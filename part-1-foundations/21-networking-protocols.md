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

Here is something that never stops being incredible: you type a URL, press Enter, and within 200 milliseconds — roughly the time it takes to blink — your browser has located a server somewhere on Earth, proved its identity through a cryptographic exchange, established a secure channel, sent a message through that channel, and received a response containing a complete webpage. Every single time. For millions of people simultaneously.

Most engineers interact with this machinery at the level of `fetch()` calls and status codes. They treat the network as a magic tube: data goes in one end, data comes out the other. This works fine until production breaks — and production always breaks — and suddenly you need to know *why* packets are being dropped between your load balancer and your backend, or *why* your API clients are getting mysterious `SSL_ERROR_RX_RECORD_TOO_LONG` errors, or *why* your service is accumulating thousands of `TIME_WAIT` connections that eventually exhaust your ephemeral port range.

This chapter is about pulling back the curtain on all of it. We will walk through TCP's handshake and congestion control algorithms, the elegant cryptographic ballet of TLS 1.3, the complete lifecycle of an HTTP request from DNS lookup to response, and the tools you use to watch all of this happen in real time. By the end, the network will not be a black box — it will be a machine you understand, and therefore a machine you can fix.

The engineers who get paged at 3 AM and actually fix things are the ones who understand these layers. That is what this chapter is building toward.

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

### The Model Underneath Everything

Every byte of data that travels between your service and the outside world passes through a stack of abstractions. Two competing reference models describe this stack. You have almost certainly heard of the OSI model — it has seven layers, from Physical up through Data Link, Network, Transport, Session, Presentation, and Application. It is a beautiful pedagogical tool that no one actually implements. The TCP/IP model has four layers, and it is how the internet actually works.

| TCP/IP Layer        | OSI Layers               | Protocols / Examples                        |
|---------------------|--------------------------|---------------------------------------------|
| Application         | Application (7), Presentation (6), Session (5) | HTTP, gRPC, DNS, TLS, SSH, SMTP  |
| Transport           | Transport (4)            | TCP, UDP, QUIC                              |
| Internet            | Network (3)              | IP (v4/v6), ICMP, ARP                       |
| Network Access      | Data Link (2), Physical (1) | Ethernet, Wi-Fi, PPP                     |

In practice, the layers you need to understand deeply are Layer 3 (IP) and Layer 4 (TCP/UDP). These are where 90% of production networking issues live. You need IP to reason about VPCs, security groups, and network policies. You need TCP to reason about connection state, latency, throughput, and reliability. The OSI model is useful as a shared vocabulary — when someone says "that is a Layer 7 issue," they mean the problem is in the application protocol, not the transport. But nobody ships software that cleanly separates the session and presentation layers.

### TCP Three-Way Handshake

Before a single byte of your HTTP request can travel to a server, TCP must establish a connection. This happens through the three-way handshake — one of the most elegant and consequential protocols in computer networking. Every web request, every database query, every API call starts with this exchange.

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

Here is what is actually happening:

1. **SYN**: The client picks an initial sequence number (ISN) `x` — a random number that protects against attackers who might try to inject packets into the connection. It sends a SYN segment and enters the `SYN_SENT` state.

2. **SYN-ACK**: The server receives the SYN, picks its own ISN `y`, and responds with SYN-ACK acknowledging the client's sequence number (`ack=x+1`). The `ack=x+1` means "I received your SYN with sequence x, I expect your next byte to be x+1." The server enters `SYN_RCVD` and allocates some resources for the connection.

3. **ACK**: The client acknowledges the server's sequence number (`ack=y+1`). Both sides enter `ESTABLISHED`. The connection is live.

The key insight here is cost: the handshake consumes one full round-trip time (RTT) before any application data flows. If your server is 50ms away, that is 50ms of overhead on every new connection — before DNS, before TLS, before HTTP. This is the foundational reason why connection reuse (pooling) is so important for performance. We will come back to this.

**SYN flood attacks** exploit the half-open state. An attacker sends millions of SYN packets with spoofed source IP addresses. The server responds with SYN-ACKs to those fake IPs and allocates a slot in its SYN queue for each — but the ACK never arrives. Eventually the SYN queue fills up and legitimate clients cannot connect. The defense is **SYN cookies** (`net.ipv4.tcp_syncookies=1`): instead of allocating state, the server encodes the connection information in the SYN-ACK's sequence number using a cryptographic hash. Only when a valid ACK arrives (carrying `ack = encoded_value + 1`) does the server allocate real resources. No queue, no attack surface.

### TCP Connection Teardown

While connection establishment is a three-way handshake, connection teardown is a four-way process — though it is often collapsed into three segments in practice. This asymmetry exists because TCP is full-duplex: each side has its own data stream and must close it independently.

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

**TIME_WAIT** is the most misunderstood state in all of TCP, and it is the source of some delightful production incidents. After the side that initiates the close sends the final ACK, it enters TIME_WAIT for 2 * MSL (Maximum Segment Lifetime — typically 60 seconds on Linux, so TIME_WAIT lasts up to 120 seconds). This exists for two essential reasons:

1. **Reliable termination**: If the final ACK is lost in transit, the remote side will retransmit its FIN. TIME_WAIT allows the local side to re-send the ACK rather than sending a confusing RST to what looks like an unrecognized connection.

2. **Preventing sequence number reuse**: Old packets from a previous connection on the same (src IP, src port, dst IP, dst port) four-tuple could still be in flight on the network. If a new connection reuses the same tuple immediately, these "zombie" packets could be misinterpreted as belonging to the new connection. TIME_WAIT ensures those segments expire before a new connection can reuse the tuple.

The real-world consequence: if your service makes many short-lived outbound connections — think: a service that creates a new connection to Redis for every request instead of pooling — you can accumulate thousands of TIME_WAIT sockets. At high enough request rates, you exhaust your ephemeral port range (typically around 28,000 ports) and start getting "Cannot assign requested address" errors. The fix is always connection pooling. The temporary mitigation is `sysctl -w net.ipv4.tcp_tw_reuse=1`, which allows reusing TIME_WAIT sockets for new outbound connections (safe for client-side use; do not use the deprecated `tcp_tw_recycle`, which was removed in kernel 4.12 because it breaks NAT).

### TCP Flow Control

TCP uses a **sliding window** mechanism to prevent a fast sender from overwhelming a slow receiver. Picture a sender trying to shove data through a garden hose — if the hose cannot carry it, the water just sprays everywhere. TCP's flow control prevents this.

The mechanism works like this:

- Each side advertises a **receive window** (`rwnd`) in every ACK — essentially announcing "I have this many bytes of buffer space, send me no more than this."
- The sender limits its unacknowledged (in-flight) data to `min(rwnd, cwnd)` where `cwnd` is the congestion window (more on this shortly).
- When the receiver's buffer fills up (rwnd = 0), the sender stops and waits. When the receiver drains its buffer and sends a window update, the sender resumes.

A critical wrinkle: the 16-bit window field in the TCP header maxes out at 65,535 bytes — only 64KB. On modern networks with multi-gigabit bandwidth and non-trivial latency, you can hit this limit easily. The solution is **window scaling** (RFC 7323), negotiated during the handshake via the Window Scale option. This multiplies the window field by a power of 2, allowing effective windows up to ~1 GB.

```bash
# Check current window sizes on Linux
ss -i | grep -A1 ESTAB
# Output includes: wscale:7,7 rto:204 rtt:1.5/0.75 cwnd:10 ssthresh:7
```

### TCP Congestion Control

Flow control handles a slow receiver. Congestion control handles a congested network — a fundamentally harder problem because the network itself does not tell you when it is overwhelmed. TCP must infer congestion from symptoms (packet loss, increased latency) and respond.

The sender maintains a **congestion window** (`cwnd`) that caps how much data can be in flight at once. The algorithms that govern cwnd are some of the most fascinating in distributed systems:

**Slow Start**: When a connection is brand new (or recovering from a timeout), cwnd starts conservatively at about 10 segments (~14KB) and *doubles every RTT*. This exponential growth continues until cwnd reaches the slow-start threshold (`ssthresh`) or packet loss is detected. "Slow" is relative — going from 10 to 10,000 segments in 10 RTTs is pretty fast.

**Congestion Avoidance**: Once `cwnd >= ssthresh`, growth becomes linear — roughly one segment per RTT (additive increase). This is the steady state for an established connection that is not experiencing loss.

**Fast Retransmit**: When the sender receives 3 duplicate ACKs — meaning the receiver got three subsequent segments but is still asking for the same missing one — it infers a single dropped segment rather than a network meltdown. It retransmits the missing segment immediately without waiting for a timeout. This is orders of magnitude faster than timeout-based recovery.

**Fast Recovery**: After fast retransmit, instead of resetting cwnd to the initial value (slow start), the sender halves cwnd (multiplicative decrease) and enters congestion avoidance. The additive-increase, multiplicative-decrease (AIMD) behavior is what allows TCP to share network bandwidth fairly among competing flows.

Now, the interesting part — the modern congestion control algorithms:

**Cubic** has been Linux's default since kernel 2.6.19. It uses a cubic function of time since the last congestion event to determine how aggressively to probe for bandwidth. Cubic performs well on high-bandwidth, high-latency links (think: trans-oceanic connections). It is loss-based — it backs off in response to packet loss, regardless of whether that loss indicates actual congestion or just a flaky wireless link.

**BBR** (Bottleneck Bandwidth and Round-trip propagation time), developed by Google, takes a radically different approach. Instead of using packet loss as a congestion signal, BBR maintains an explicit model of the network path: it continuously estimates the actual bottleneck bandwidth and the minimum round-trip propagation time. It then paces packet transmission to match the bottleneck bandwidth without overfilling buffers. On networks with shallow buffers or random packet loss (wireless, for instance), BBR dramatically outperforms Cubic. It powered a significant improvement in YouTube throughput when Google deployed it. The catch: BBR can be aggressive and unfair to competing Cubic flows in certain configurations.

```bash
# Check current congestion control algorithm
sysctl net.ipv4.tcp_congestion_control
# Switch to BBR (requires kernel 4.9+)
sysctl -w net.ipv4.tcp_congestion_control=bbr
```

### TCP vs UDP

TCP's reliability guarantees come with overhead. UDP strips all of that away: no connection setup, no acknowledgment, no ordering, no retransmission. You get raw datagram delivery.

| Property              | TCP                      | UDP                         |
|-----------------------|--------------------------|-----------------------------|
| Delivery guarantee    | Reliable, ordered        | Best-effort, unordered      |
| Connection setup      | Three-way handshake      | None (connectionless)       |
| Head-of-line blocking | Yes                      | No                          |
| Flow/congestion ctrl  | Built-in                 | None (app must implement)   |
| Header size           | 20-60 bytes              | 8 bytes                     |
| Use cases             | HTTP, databases, SSH     | DNS, video streaming, gaming, QUIC |

**When UDP makes sense:**

- **DNS queries**: A single request-response. The overhead of a TCP handshake would more than double the latency of a query that should take 1ms.
- **Real-time audio/video**: A retransmitted packet that arrives 200ms late is useless — you have already moved on to the next frame. Better to skip than to stall.
- **Online gaming**: Player position updates arrive at 60Hz. By the time a retransmitted packet from 33ms ago arrives, you have already received five newer updates that supersede it.
- **QUIC** (HTTP/3): The most interesting case — QUIC builds its own reliability on top of UDP specifically to avoid the head-of-line blocking inherent in TCP. More on this in the HTTP/3 section.

**When to use TCP:** Everything where data integrity matters and you do not want to re-implement reliability yourself. This is most things.

### Socket Programming Concepts

At the OS level, all of this happens through sockets — file descriptors that represent network endpoints. Understanding the lifecycle demystifies a lot of production configuration.

**Server lifecycle:**
```
socket()  →  bind()  →  listen()  →  accept()  →  read()/write()  →  close()
```

**Client lifecycle:**
```
socket()  →  connect()  →  read()/write()  →  close()
```

Some important nuances:

- `listen(fd, backlog)`: The `backlog` parameter controls how many *completed* handshakes can queue up before `accept()` is called. On Linux, there is also a separate SYN queue that holds in-progress handshakes. If either queue fills up, new connections are dropped (SYN queue) or silently queued (accept queue, up to the backlog limit). A backlog that is too small causes dropped connections under sudden load spikes.

- `accept()`: Returns a brand new file descriptor for each accepted connection. The original listening socket continues to accept more connections — it is a factory, not a pipe.

- **File descriptors**: Every socket is a file descriptor. The system-wide limit (`ulimit -n`, `fs.file-max`) is a hard ceiling. At 10,000 concurrent connections with some additional file descriptors for logs and configuration, you can hit the default limit of 1024 on a misconfigured system. Every high-performance server sets this to at least 100,000.

**I/O multiplexing** is the solution to handling thousands of connections without spawning a thread for each:

- **`select`/`poll`**: Both take a list of file descriptors and block until one is ready. They are O(n) per call — you scan the entire list every time. This becomes the bottleneck above ~1,000 connections.
- **`epoll`** (Linux): Instead of scanning, you register file descriptors once and get notified only when they are ready. O(1) per event. This is the engine inside nginx, Node.js, and Go's network runtime. It is why a single nginx process can handle tens of thousands of concurrent connections.
- **`kqueue`** (macOS/BSD): The BSD equivalent of epoll. Same O(1) semantics.

```bash
# See how many file descriptors a process is using
ls /proc/<pid>/fd | wc -l
# Check system-wide limits
sysctl fs.file-max
# Check per-process limits
ulimit -n
```

### TCP_NODELAY and Nagle's Algorithm

Nagle's algorithm is a beautiful optimization from 1984 that remains a common source of latency bugs today. The observation: small TCP segments waste bandwidth because the protocol overhead (40 bytes of IP + TCP headers) exceeds the payload. Nagle's solution: buffer small writes and combine them into larger segments. Specifically, it holds data until either (a) there is enough data to fill a full-size segment, or (b) all previously sent data has been acknowledged.

For bulk file transfer, this is great. For interactive protocols, it is catastrophic. Here is the scenario: you send a 50-byte RPC request. Nagle's algorithm holds it, waiting for the ACK from the *previous* request before releasing it. That ACK takes one RTT — potentially 100ms. During that 100ms, your 50-byte request sits in a buffer going nowhere. Combine this with TCP's delayed ACK (receivers wait up to 200ms before sending ACK to batch them), and you can end up in a situation where both sides are waiting for the other, adding hundreds of milliseconds of completely artificial latency.

**`TCP_NODELAY`** disables Nagle's algorithm. Every `write()` is sent immediately.

**When to set TCP_NODELAY:**
- RPC protocols (gRPC, Redis protocol, database wire protocols)
- Interactive sessions (SSH, telnet)
- Any protocol where latency matters more than bandwidth efficiency

Most modern HTTP libraries and database drivers set `TCP_NODELAY` by default. But if you are implementing a custom protocol or using a lower-level library, you need to set it explicitly.

### Keep-Alive vs Connection Pooling

**TCP keep-alive** is an OS-level mechanism that sends probe packets on idle connections to detect whether the remote end has silently disappeared. Without it, if a server crashes or a network path goes down mid-connection, the client might sit with a half-open connection for hours — trying to send data into a void.

On Linux, keep-alive is controlled by three parameters:

```bash
# Default: probe after 2 hours of inactivity
sysctl net.ipv4.tcp_keepalive_time      # 7200 seconds
sysctl net.ipv4.tcp_keepalive_intvl     # 75 seconds between probes
sysctl net.ipv4.tcp_keepalive_probes    # 9 probes before declaring dead
```

The 2-hour default is a land mine in cloud environments. AWS NLB has an idle timeout of 350 seconds. If TCP keep-alive does not fire before the load balancer's timeout, the LB silently drops the connection. The next request gets a RST or timeout, and your application sees a mysterious connection error. Always configure keep-alive timeouts shorter than any intermediary's timeout.

**Connection pooling** operates at the application layer and addresses a different problem: the overhead of establishing new connections. Every new TCP connection costs at minimum 1 RTT for the handshake, plus another 1-2 RTTs for TLS. At 30ms round-trip time, that is 60-90ms of overhead before any application data flows — for every single request.

```
Without pooling: DNS + TCP (1 RTT) + TLS (1-2 RTT) + Request/Response = 3-4 RTTs
With pooling:    Request/Response = 1 RTT (connection already established)
```

Connection pooling is not a nice-to-have. For any service making frequent outbound calls — to a database, a cache, an external API — it is the difference between a service that works and one that cannot handle production load.

### Common TCP Problems

**TIME_WAIT accumulation**: If your service makes many short-lived outbound connections, each closed connection sits in TIME_WAIT for 60 seconds. At high rates, you can exhaust the ephemeral port range (typically 28,000 ports).

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

**Connection reset (RST)**: A RST packet abruptly terminates a connection with no ceremony. Common causes: connecting to a port with no listener, an application that crashed without closing its socket, a firewall or load balancer timing out and sending RST on behalf of a gone endpoint, or sending data on a half-closed connection.

**Half-open connections**: One side thinks the connection is open; the other side has crashed or lost network. The "open" side will not discover this until it tries to send data (and gets RST or timeout) or until TCP keep-alive detects it. This is why keep-alive matters even for connections you believe are "active."

---

## 2. TLS & Encryption on the Wire

### The Brilliant Engineering of TLS 1.3

In 2018, after a decade of TLS 1.2 accumulating a graveyard of deprecated ciphers and attack surface, the IETF published TLS 1.3 (RFC 8446). It is a masterpiece of protocol design: more secure, faster, and conceptually cleaner than its predecessor. Understanding it is not just academic — it is visible in your production latency numbers.

The key innovation: in TLS 1.2, the client first says hello, the server responds with what crypto it supports, *then* they exchange keys. That is two round trips before any encrypted data can flow. TLS 1.3 collapses this: the client sends its key material in the very first message, gambling that it can correctly guess which algorithm the server prefers. In practice, this gamble almost always pays off.

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

1. **ClientHello**: The client sends its supported TLS versions, cipher suites, a random nonce, and critically — a **key_share** — its half of the Diffie-Hellman key exchange (typically an X25519 or P-256 ephemeral public key). This is the key optimization: the client guesses which key exchange the server will accept and sends its share preemptively.

2. **ServerHello**: The server selects a cipher suite and sends its own key_share. At this point, both sides can derive the handshake keys using Elliptic Curve Diffie-Hellman Ephemeral (ECDHE). Everything after ServerHello is encrypted — the certificate, the extensions, everything. An eavesdropper watching TLS 1.3 traffic sees far less than in TLS 1.2.

3. **Encrypted payload**: The server sends its certificate, a signature proving it owns the private key (CertificateVerify), and a Finished message (a MAC over the entire handshake transcript, preventing tampering).

4. **Client Finished**: The client verifies the certificate chain, checks the signature against the server's public key, and sends its own Finished message. Application data can be sent along with this message.

**Result**: 1 RTT total. The client can send its first HTTP request in the same flight as the TLS Finished message.

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

The most important change is **mandatory Perfect Forward Secrecy (PFS)**. In TLS 1.2 with RSA key exchange, the server's private key was directly involved in each session's key derivation. If an attacker recorded encrypted traffic today and obtained the server's private key years later, they could decrypt every conversation. This is the "harvest now, decrypt later" threat model, and it is not hypothetical — nation-state actors are believed to do exactly this.

TLS 1.3 eliminates the possibility by requiring ephemeral key exchange. Every session generates fresh key material that is discarded after use. Even if the server's long-term private key is compromised tomorrow, past sessions remain mathematically unrecoverable. This is PFS: the security of past sessions does not depend on the secrecy of long-term keys.

### 0-RTT Resumption — Speed With a Caveat

TLS 1.3 supports an optimization called 0-RTT (early data): if a client has connected to a server before, it can send application data in the very first flight — alongside the ClientHello — using a pre-shared key (PSK) from the previous session.

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

This sounds miraculous, but there is a real security caveat: **0-RTT data is not protected against replay attacks**. An attacker who captures the first flight of a TLS handshake can re-send it to the server, causing the server to process the 0-RTT data again. For idempotent reads (GET requests, cacheable queries), this is fine. For mutating operations (POST creating a payment, PUT updating a balance), it is dangerous.

Servers can mitigate replay by maintaining a list of used session tickets (at the cost of statefulness and single-datacenter scope) or by accepting 0-RTT only within a short time window. The practical rule: **use 0-RTT only for genuinely idempotent requests**. Most CDNs and edge proxies that implement 0-RTT follow this guideline automatically, converting 0-RTT data for non-GET methods into standard 1-RTT requests.

### Certificate Chain Validation

When a server presents its certificate, the client does not just check if it looks legit — it validates a cryptographic chain from the server's certificate back to a root that the client trusts inherently. This chain of trust is the foundation of HTTPS security.

```
Root CA (e.g., DigiCert Global Root G2)
  └── Intermediate CA (e.g., DigiCert SHA2 Extended Validation Server CA)
        └── Leaf Certificate (e.g., CN=api.example.com)
```

The validation process:

1. **Chain building**: The leaf cert's "Issuer" field must match the intermediate's "Subject." The intermediate's "Issuer" must match the root's "Subject."
2. **Signature verification**: Each certificate's signature is verified using the issuer's public key. This forms an unbroken cryptographic chain.
3. **Root trust**: The root CA must be in the client's trust store — the curated list of CAs that OS vendors and browser makers have decided to trust. Getting onto this list requires an extensive audit process.
4. **Validity period**: Each certificate must be within its `notBefore` and `notAfter` dates.
5. **Revocation check**: Verify the certificate has not been revoked via OCSP or CRL.
6. **Name matching**: The leaf certificate's Subject Alternative Name (SAN) must match the hostname the client requested.

**One of the most common production issues**: the server is configured with only the leaf certificate, omitting the intermediate. Modern browsers are sophisticated — they often cache intermediate certificates from previous connections and can complete the chain themselves. But API clients (`curl`, Python `requests`, Go's `http.Client`) perform strict chain validation and will fail with "certificate verify failed" or "unable to verify the first certificate." Always configure the full chain on your server. Most TLS libraries have a way to specify an "intermediate bundle" alongside the leaf certificate.

### Certificate Pinning

Certificate pinning is the practice of hardcoding the expected certificate (or more precisely, a hash of its public key) in the client. Rather than trusting any certificate signed by a trusted CA, the client will only trust a specific certificate or key.

**When pinning makes sense:**
- Mobile apps communicating with a known backend you control
- Service-to-service communication where you own both ends

**When to avoid pinning:**
- Websites (browsers deprecated HTTP Public Key Pinning / HPKP because misconfigured pins can permanently lock users out of your site — there is no recovery except waiting for pin expiry)
- Any situation where you cannot guarantee timely client updates when certificates rotate

If you do pin, the best practice is to **pin the public key hash of the intermediate CA** rather than the leaf. Leaf certificates rotate every 90 days (or less with Let's Encrypt). Intermediate CAs rotate rarely — typically every 5-10 years. Also always pin at least two keys (primary + backup intermediate) to avoid lockout when rotation happens.

### SNI (Server Name Indication)

Before SNI existed, hosting multiple HTTPS domains on a single IP address was essentially impossible. The server had to present its certificate before knowing which domain the client was requesting — the hostname comes in the HTTP request, which is inside the encrypted TLS session, which requires the certificate to decrypt. A chicken-and-egg problem.

SNI breaks this deadlock: the client includes the requested hostname in the TLS ClientHello itself, before encryption begins. The server reads the SNI extension, selects the appropriate certificate, and the handshake proceeds.

There is a privacy implication: SNI is sent in **plaintext** in both TLS 1.2 and TLS 1.3. Anyone on the network path — your ISP, a Wi-Fi operator, a government monitoring infrastructure — can see which hostname you are connecting to, even though the actual traffic is encrypted. **Encrypted Client Hello (ECH)** is the IETF's answer: it encrypts the entire ClientHello (including SNI) using a public key the server publishes via DNS. As of 2026, ECH is widely supported by Cloudflare, Firefox, and Chrome, but not yet universal.

Almost all modern TLS clients send SNI. If you are reading this in 2026, you can safely require SNI for your services — the only clients that do not send it are genuinely ancient (Android 2.x, IE on Windows XP).

### mTLS (Mutual TLS)

In standard TLS, only the server proves its identity to the client. mTLS goes both directions: the client also presents a certificate, and the server verifies it. This provides cryptographically strong authentication at the transport layer, without relying on API keys or session tokens.

**Use cases:**
- Service-to-service authentication in microservices (Istio service mesh uses mTLS by default for all inter-service communication)
- API authentication where API keys are insufficient
- Zero-trust network architectures where you never trust network location alone

**How the handshake extends:**
1. After the server sends its certificate, it includes a `CertificateRequest` message asking the client to identify itself.
2. The client responds with its own certificate and a `CertificateVerify` signature proving it holds the corresponding private key.
3. The server validates the client certificate against its trusted CA, and the connection is established with mutual authentication.

**The operational challenge**: you now need to manage certificates for every client in your system. At scale, this means PKI infrastructure. Tools like HashiCorp Vault PKI, cert-manager on Kubernetes, and SPIFFE/SPIRE exist specifically to automate this certificate lifecycle management. Istio's approach — using SPIFFE-compliant certificates automatically rotated every 24 hours — is worth studying as a model for how to do mTLS at scale without turning your engineers into full-time certificate administrators.

### OCSP Stapling vs CRL

When a certificate is compromised — say, an attacker obtains a server's private key — the CA needs to revoke it. But how does a client know a certificate has been revoked? This is the revocation problem, and the solutions are more complicated than you would expect.

**CRL (Certificate Revocation List)**: The CA publishes a list of revoked certificate serial numbers. Clients download the list and check it. Problems: CRLs can grow large (megabytes), downloads add latency, and clients often silently skip the check (soft-fail mode) when the CRL is unavailable. Real-world studies have shown that CRL checking often effectively does nothing.

**OCSP (Online Certificate Status Protocol)**: The client sends the certificate's serial number to the CA's OCSP responder (an HTTP endpoint) and receives a signed "good/revoked/unknown" response. Fresher than CRL, but still adds a serial round-trip to every TLS handshake, the CA sees which sites you visit (a privacy leak), and OCSP responders can themselves be slow or unavailable.

**OCSP Stapling** is the elegant solution. The *server* periodically fetches the OCSP response from the CA and caches it. During the TLS handshake, the server "staples" this pre-fetched response to the handshake. The client gets proof of non-revocation — signed by the CA — without contacting the CA at all. No added latency, no privacy leak, and the response is still CA-signed so the server cannot forge it.

Enable OCSP stapling on every public-facing TLS server. It is a straightforward configuration option in nginx, Apache, and HAProxy.

```bash
# Check if a server supports OCSP stapling
openssl s_client -connect api.example.com:443 -status < /dev/null 2>&1 | grep -A5 "OCSP Response"
```

### Let's Encrypt and the ACME Protocol

Before Let's Encrypt launched in 2015, getting a TLS certificate required paying a CA, going through a manual verification process, and downloading files. Let's Encrypt made certificates free and automated the entire process using the ACME (Automatic Certificate Management Environment) protocol. It changed the web: HTTPS went from optional to default in just a few years.

**How ACME works:**
1. The client (certbot, Caddy, Traefik, or any ACME-compatible tool) creates an account with the ACME server.
2. The client requests a certificate for a domain.
3. The ACME server issues a challenge to prove the client controls the domain:
   - **HTTP-01**: Place a specific file at `http://<domain>/.well-known/acme-challenge/<token>`. The ACME server fetches it to verify.
   - **DNS-01**: Create a TXT record at `_acme-challenge.<domain>`. Required for wildcard certificates (`*.example.com`) because those cannot be verified via HTTP.
   - **TLS-ALPN-01**: Respond to a TLS connection on port 443 with a special self-signed certificate containing the challenge token. Useful when port 80 is blocked.
4. Once the client completes the challenge, the ACME server issues the certificate.

Let's Encrypt certificates are valid for 90 days. This is intentional: short lifetimes force automation and limit the damage window if a certificate is compromised. Most ACME clients handle renewal automatically (certbot installs a systemd timer or cron job that checks twice daily and renews when less than 30 days remain). Caddy and Traefik do this transparently with no configuration.

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

### What Happens in the 200 Milliseconds After You Press Enter

This is the most important mental model in backend engineering. Every time a client makes an HTTPS request — your mobile app hitting an API, your frontend calling a service, your service calling another service — this exact sequence plays out. Understanding each step is what allows you to optimize performance, debug failures, and design systems that actually work under load.

Let us trace `https://api.example.com/users/123` from the keystroke to the response.

#### Step 1: DNS Resolution

The HTTP client needs to know the IP address of `api.example.com`. DNS resolution happens in layers, each with its own cache:

1. **Browser DNS cache**: Chrome has its own DNS cache, accessible at `chrome://net-internals/#dns`. Records are cached with their TTL.
2. **OS DNS cache**: If the browser cache misses, the query goes to the operating system. On Linux: `systemd-resolved` or `nscd`. On macOS: `mDNSResponder`.
3. **Recursive resolver**: If the OS cache misses, the query goes to the configured recursive resolver — typically your router's address (which forwards to your ISP), or a configured public resolver like `8.8.8.8` or `1.1.1.1`. This resolver has its own cache.
4. **Root nameservers → TLD nameservers → Authoritative nameserver**: If the recursive resolver has nothing cached, it walks the DNS tree from root to authoritative, fetching and caching each referral. (More on this in Section 4.)

The result is an IP address: `93.184.216.34`. Total time: 0ms if cached, up to 200ms on a cold cache requiring a full recursive resolution.

#### Step 2: TCP Connection

The client opens a TCP connection to port 443 on the resolved IP:

```
SYN  →  (network latency)  →  SYN-ACK  →  (network latency)  →  ACK
```

Cost: 1 RTT. If the server is 30ms away, this takes 30ms. With connection pooling — where this connection was established on a previous request and is being reused — this cost drops to zero.

#### Step 3: TLS Handshake

With TLS 1.3: 1 additional RTT before data can flow. With TLS 1.2: 2 RTTs. If the client has a session ticket from a recent connection (and 0-RTT is configured): the first data can be sent immediately, with no additional RTT for the handshake.

#### Step 4: HTTP Request

Over the now-encrypted connection, the client sends the HTTP request:

```http
GET /users/123 HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
User-Agent: MyApp/1.0
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

#### Step 5: Server Processing

The server receives the request bytes, parses the HTTP, validates the `Authorization` header, queries the database, applies business logic, and serializes the response. This is the part you control. Every millisecond here is yours to optimize.

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

The connection does not close after the response. HTTP/1.1 keep-alive (the default) keeps it open for subsequent requests. HTTP/2 goes further — multiple requests can fly across the same connection simultaneously. This connection reuse is the mechanism that makes connection pooling so effective.

**Total latency, cold start:**
```
DNS lookup:        ~50ms (uncached)
TCP handshake:     ~30ms (1 RTT)
TLS handshake:     ~30ms (1 RTT with TLS 1.3)
HTTP req/response: ~30ms (1 RTT) + server processing time
──────────────────────────────────
Total:             ~140ms + server processing
```

**With connection pooling and warm DNS cache:**
```
HTTP req/response: ~30ms (1 RTT) + server processing
```

That is a 4x reduction in overhead per request. At 1,000 requests per second, you are saving 110ms × 1,000 = 110 seconds of latency *per second*. Connection pooling is not optional for production systems.

### HTTP/1.1 vs HTTP/2 vs HTTP/3

The HTTP protocol has evolved dramatically, driven by one recurring villain: latency.

#### HTTP/1.1

HTTP/1.1, standardized in 1997 and still widely used, has one fundamental limitation: **one request per connection at a time**. To make concurrent requests, the client must open multiple TCP connections — browsers typically allow 6 per hostname. This burns TCP connection slots, triggering multiple handshakes, and TLS stacks on top of that. Header compression does not exist in HTTP/1.1 — the same verbose headers get sent in plain text on every single request.

- **Text-based headers**: Sent as ASCII on every request, with no compression.
- **Chunked transfer encoding**: The server can stream response bodies of unknown size by sending chunks with their length prepended.
- **Pipelining**: Technically specified in HTTP/1.1 — you can send multiple requests without waiting for responses. In practice, no major browser or server implemented this correctly due to head-of-line blocking (responses must arrive in order, so one slow response blocks everything behind it).

#### HTTP/2 (RFC 7540)

HTTP/2, deployed starting around 2015, was designed around one core insight: the protocol itself was causing performance problems, and fixing it required going binary.

- **Multiplexing**: Multiple request-response pairs are interleaved on a single TCP connection using numbered **streams**. Stream 1 might be fetching the HTML, stream 3 the CSS, stream 5 a JavaScript file — all flying across the wire simultaneously. No artificial 6-connection limit needed.

- **Header compression (HPACK)**: Both sides maintain a shared dynamic table of previously-seen headers. After the first request, common headers like `Host`, `Accept`, `Authorization` can be represented as single integers referencing the table. Typical header overhead drops from ~800 bytes to ~20 bytes.

- **Server push**: The server can proactively send resources the client will probably need — push the CSS when the HTML is requested, before the client even parses the HTML and realizes it needs CSS. In practice, this was difficult to use correctly (you push resources the client already has cached) and Chrome removed support in 2022.

- **Binary framing**: The protocol is binary, not text. Each frame has a fixed header format (9 bytes), followed by a payload. This is more efficient to parse and less error-prone than HTTP/1.1's text format.

**The remaining problem**: HTTP/2 runs over TCP, which delivers bytes in strict sequence. When a TCP segment carrying part of one HTTP/2 stream is lost and must be retransmitted, *all* HTTP/2 streams on that connection stall — even streams that had no data in the lost segment. TCP has no concept of independent streams; from its perspective, it is just bytes. This **TCP head-of-line blocking** is the fundamental limitation that motivated HTTP/3.

#### HTTP/3 (RFC 9114)

HTTP/3 solves the TCP problem at its root by eliminating TCP entirely.

- **Built on QUIC**: QUIC is a transport protocol implemented over UDP. It provides reliable, ordered delivery — but per-stream rather than per-connection. A packet loss on stream 1 does not affect stream 3. Each stream has independent flow control and retransmission.

- **No TCP head-of-line blocking**: A lost packet only stalls the one stream it belongs to. Other streams continue flowing.

- **Faster connection establishment**: QUIC combines the transport handshake and TLS 1.3 into a single 1-RTT exchange. Resumed connections can use 0-RTT.

- **Connection migration**: QUIC connections are identified by a connection ID, not the IP address and port tuple. If you walk from your desk to a conference room and switch from Wi-Fi to the office network — getting a new IP address — a QUIC connection can migrate seamlessly. Your download continues without interruption.

- **QPACK**: Header compression adapted for QUIC, handling the fact that QUIC streams can arrive out of order (unlike HTTP/2's streams, which are constrained by TCP's ordering).

HTTP/3 is now supported by all major browsers and CDNs. As of 2026, roughly 30% of web traffic uses HTTP/3.

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

Status codes are a contract between your API and its clients. Using the right one matters — a miscoded status code can break caching, confuse retry logic, and mislead monitoring alerts.

**2xx — Success:**
- `200 OK`: Request succeeded. The canonical success response.
- `201 Created`: Resource created (typically for POST). Should include a `Location` header pointing to the new resource.
- `204 No Content`: Success, but there is no body to return. Correct for DELETE and sometimes PUT.

**3xx — Redirection:**
- `301 Moved Permanently`: The resource is permanently at a new URL. Cacheable. Browsers (but not all HTTP clients) will change POST to GET when following this redirect.
- `302 Found`: Temporary redirect. Browsers change POST to GET on follow (use 307 to preserve the method).
- `304 Not Modified`: The conditional request matched — the cached version is still valid. The client should use its cached copy. Works with `If-None-Match`/`ETag` and `If-Modified-Since`/`Last-Modified`.

**4xx — Client Error:**
- `400 Bad Request`: The request is malformed — invalid JSON, missing required field, impossible parameter value.
- `401 Unauthorized`: Authentication is required or the provided credentials are invalid. Should include a `WWW-Authenticate` header telling the client how to authenticate.
- `403 Forbidden`: Authenticated, but not authorized for this resource. Do not retry with the same credentials — they are valid but insufficient.
- `404 Not Found`: The resource does not exist.
- `409 Conflict`: The request conflicts with the current state — duplicate email on user creation, trying to delete a non-empty resource, optimistic locking failure.
- `429 Too Many Requests`: Rate limit exceeded. Always include a `Retry-After` header.

**5xx — Server Error:**
- `500 Internal Server Error`: An unhandled exception on the server. This is a bug in your code.
- `502 Bad Gateway`: The reverse proxy received an invalid response from the upstream. Usually means the upstream process crashed or returned garbage.
- `503 Service Unavailable`: Temporarily overloaded or in maintenance. Should include `Retry-After`.
- `504 Gateway Timeout`: The reverse proxy timed out waiting for the upstream. The upstream is alive but too slow.

**Debugging heuristic**: 502 usually means the upstream process is dead or returned garbage. 504 usually means the upstream is alive but too slow. Both indicate the problem is *upstream* of wherever you see the error — the service returning 502/504 is often innocent.

### Connection Pooling in Practice

Creating a new TCP connection per request is catastrophic for performance at scale:

```
Without pooling (per-request connection):
  DNS + TCP + TLS + Request + Response + Close = ~200ms overhead per request

With pooling (reused connection):
  Request + Response = ~30ms overhead per request
```

Every production HTTP client must use connection pooling. Most do by default, but with configurations that need tuning:

- **Go**: `http.Client` uses `http.Transport`, which pools by default. The critical setting: `MaxIdleConnsPerHost`, which defaults to 2. For a service making thousands of requests per second to the same host, 2 idle connections is almost certainly not enough — increase to 50-100.
- **Python requests**: You must use a `Session` object. A bare `requests.get()` call creates a new connection every time.
- **Node.js**: `http.Agent` pools connections. Set `keepAlive: true` (default since Node 19).
- **Java**: `HttpClient` pools by default in modern versions.

```bash
# Monitor connection pool behavior — look for connection reuse vs new connections
curl -v https://api.example.com/users/1 https://api.example.com/users/2 2>&1 | grep -E 'Connected|Re-using'
```

---

## 4. DNS Resolution Deep Dive

### The Invisible Infrastructure That Routes Everything

DNS is one of the oldest and most underappreciated parts of the internet. It translates human-readable names into machine-routable IP addresses — a distributed database with billions of records, queried trillions of times per day, without any central coordinator. Understanding its mechanics is essential not just for debugging, but for disaster prevention.

### Full Resolution Path

Every DNS query travels through a hierarchy:

```
Browser cache → OS cache → Recursive resolver cache → Root (.) → TLD (.com) → Authoritative (example.com)
```

The recursive resolver (Cloudflare 1.1.1.1, Google 8.8.8.8, your ISP's resolver, or your corporate DNS) does the heavy lifting. When it receives a query it cannot answer from cache:

1. It queries a **root nameserver** — there are 13 logical root server clusters (labeled a through m), distributed globally via anycast at addresses like `198.41.0.4`. The root knows nothing about individual domains, but it knows where to find the TLD servers.

2. The root returns a referral to the **.com TLD nameserver** (operated by Verisign). The resolver queries it.

3. The TLD nameserver returns a referral to the **authoritative nameserver** for `example.com` — the server your DNS provider runs. The resolver queries it.

4. The authoritative nameserver returns the actual answer: the A record for `api.example.com`.

5. The resolver caches the result according to the TTL and returns it to the client.

This whole process takes 50-200ms on a cold cache — but almost all production queries hit cache. The recursive resolver's cache is shared across all its clients, so popular domains like `google.com` or `amazonaws.com` are almost always cached. The cold-start penalty matters mainly for newly created records or low-traffic domains.

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

### TTL and Caching Behavior — The Secret Lever

The TTL (Time to Live) is the most important and most misunderstood DNS setting. It tells resolvers how many seconds to cache a record before they must re-query the authoritative server.

- **Low TTL (30-60 seconds)**: Changes propagate quickly. Essential for failover scenarios where you need to redirect traffic within minutes. The cost: higher query load on your authoritative nameservers, and some resolvers enforce a minimum TTL floor (some ISP resolvers floor at 300 seconds regardless of what you set).

- **High TTL (3600+ seconds)**: Reduces query load and provides resilience — if your authoritative nameserver goes down, resolvers continue serving cached records until the TTL expires. The cost: changes are slow to propagate.

**Negative caching** catches many people off guard: when a query returns NXDOMAIN (the record does not exist), resolvers cache *that negative result* too — based on the SOA record's minimum TTL. If you create a new DNS record for a hostname that previously returned NXDOMAIN, some resolvers will continue returning NXDOMAIN until their negative cache entry expires.

**Practical recipe for migrations**: Use TTL of 300 seconds (5 minutes) for most records. Before a major DNS change:
1. Reduce TTL to 60 seconds.
2. Wait for the original TTL to expire (so the reduced TTL is now what resolvers have cached).
3. Make the DNS change.
4. Within 60 seconds, the new value is live everywhere.

### DNS Propagation — Debunking the Myth

"DNS takes 24-48 hours to propagate" is a persistent myth that has caused unnecessary downtime and delayed countless migrations. It originated when it was common to set TTLs to 86400 seconds (24 hours). With those TTLs, the math was correct. With modern TTLs, it is not.

Here is the truth: **DNS propagation is just cache expiry.** There is no global synchronization mechanism. No message goes out to all resolvers saying "please update your cache." Resolvers simply serve their cached answer until the TTL expires, then re-query. If you set a TTL of 60 seconds, your DNS change reaches every properly-configured resolver within 60 seconds.

The caveats:
- Some resolvers enforce minimum TTL floors (typically 30-300 seconds).
- Some CDNs and corporate DNS caches have aggressive internal caching that can exceed the TTL.
- Old browsers or applications might cache DNS records beyond the TTL specified (a bug, but it happens).

These pockets of stale resolution are real but narrow. For most purposes, if you reduce your TTL to 60 seconds and wait out the previous TTL, your DNS change is effectively instant.

### DNS-Based Load Balancing

DNS is one of the original load balancing mechanisms, and managed DNS providers have made it surprisingly powerful:

- **Round-robin**: Return multiple A records for the same hostname. DNS clients (and the OS) typically try them in order. Simple but offers no health checking — if one server is down, clients will still try its IP until they time out.

- **Weighted**: Return records with different frequencies to distribute traffic proportionally. Send 80% of traffic to a new deployment, 20% to the old one — classic canary deployment via DNS.

- **Latency-based**: Route to the region with the lowest measured latency from the resolver's geographic location (AWS Route 53 latency routing). The resolver's location is used as a proxy for the client's location, which is not always accurate but is usually good enough.

- **Geolocation**: Route based on the resolver's geographic location. Useful for data residency requirements (GDPR compliance: EU clients must go to EU servers) or serving localized content.

- **Failover**: Return the primary IP normally; return a secondary IP only when health checks detect the primary is unreachable. Route 53 health checks your endpoint every 30 seconds and can switch routing in under a minute.

All of these are implemented at the authoritative nameserver level and are features of managed DNS services (Route 53, Cloudflare DNS, Google Cloud DNS).

### DNS over HTTPS (DoH) and DNS over TLS (DoT)

Traditional DNS uses unencrypted UDP on port 53. This is a privacy and security disaster: your ISP, your Wi-Fi operator, and anyone else on your network path can see every domain you query. They can also modify responses — redirecting you to a different IP, or injecting ads into NXDOMAIN responses (a practice some ISPs used for years).

- **DoT (DNS over TLS, RFC 7858)**: Wraps DNS queries in TLS on port 853. The content is encrypted, but the distinctive port makes it easy for ISPs and enterprise networks to block or intercept.

- **DoH (DNS over HTTPS, RFC 8484)**: Sends DNS queries as standard HTTPS POST or GET requests to an endpoint like `https://cloudflare-dns.com/dns-query`. Encrypted and indistinguishable from normal HTTPS traffic. This makes it difficult for network operators to block without blocking all HTTPS, which is why enterprise IT departments have complicated feelings about it.

Both are widely deployed. Firefox uses DoH by default in the US (routing through Cloudflare or NextDNS). Chrome supports DoH. Operating systems are adding native DoT/DoH support — iOS 14+, Android 9+, Windows 11 all have it built in.

### Common DNS Problems in Production

**Stale cache**: A resolver is returning an old IP after you changed the record. Wait for the TTL to expire. If it is urgent:

```bash
# Flush macOS DNS cache
sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder

# Flush systemd-resolved cache (Linux)
sudo systemd-resolve --flush-caches
```

**TTL too low → query storms**: If your TTL is 5 seconds and you have 10,000 servers, each server queries the authoritative nameserver every 5 seconds. That is 2,000 queries/second to your DNS server. Use a local caching resolver (systemd-resolved, dnsmasq, unbound) on each host — it shares the cache among all local processes.

**TTL too high → slow failover**: If your TTL is 3600 seconds and your primary server dies, clients keep trying the dead IP for up to an hour. Balance TTL against your failover time requirement.

**CNAME at zone apex**: You cannot place a CNAME at the root of your domain (`example.com`), only at subdomains (`www.example.com`). The root of a zone must have SOA and NS records, and DNS prohibits CNAME from coexisting with other record types at the same name. Solutions: use ALIAS or ANAME records (provider-specific synthetic record types that behave like CNAME but are resolved server-side), or simply use A records with your load balancer's IP.

### DNS Propagation Disasters and How to Avoid Them

DNS misconfigurations have caused some memorable outages. The pattern is usually: someone changes a DNS record with a high TTL, the change is wrong, and now the damage is baked into resolvers worldwide for hours. The recovery involves fixing the record and then... waiting. That is it. You cannot force the world to un-cache a record.

Two practices prevent most DNS disasters:

1. **Reduce TTL before making changes.** Set TTL to 60-300 seconds, wait for the old TTL to expire, then make your change. If something goes wrong, recovery is fast.

2. **Test before cutting over.** Use `dig @<authoritative-server> <hostname>` to verify your change at the authoritative level before it propagates. You can also test against the new IP directly using `curl --resolve`.

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

### The Revolution in Real-Time Communication

Before WebSockets, building real-time web applications required creative abuse of HTTP. Long polling — where the client sends a request and the server holds it open until there is data to send — worked, but consumed a server thread or process per connected client. Comet, various iframe tricks, forever-frames... the solutions were baroque.

WebSocket, standardized in 2011 (RFC 6455), was the elegant solution: a persistent, full-duplex connection between browser and server, initiated via HTTP and then upgraded to its own binary frame protocol. It enabled a generation of real-time applications — collaborative editing, live dashboards, multiplayer games, trading platforms — that would have been impractical before.

### The WebSocket Handshake

WebSocket starts as a perfectly ordinary HTTP/1.1 request with one special header. This is intentional — it allows WebSocket connections to work through existing HTTP infrastructure, proxies, and servers without special configuration. After the handshake, the protocol completely transforms.

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

The `Sec-WebSocket-Accept` value is computed by concatenating the client's `Sec-WebSocket-Key` with a magic GUID (`258EAFA5-E914-47DA-95CA-5AB5DC11CE56`), computing the SHA-1 hash, and base64-encoding it. This dance proves that the server actually understands the WebSocket protocol and is not, say, a naive HTTP proxy blindly echoing requests. The magic GUID was chosen to be unforgeable without knowing the spec.

After the 101 Switching Protocols response, both sides switch to the WebSocket frame format over the same underlying TCP connection. HTTP is done.

### Frame Format

The WebSocket wire format is elegantly minimal:

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

- **FIN bit**: 1 = this is the final (or only) fragment of a message. 0 = more fragments follow. Large messages can be split across multiple frames.
- **Opcode**: Determines what the frame carries. `0x1` = text frame (UTF-8 string), `0x2` = binary frame, `0x8` = close, `0x9` = ping, `0xA` = pong, `0x0` = continuation frame for a fragmented message.
- **MASK bit**: Client-to-server frames **must** be masked (XORed with a 32-bit masking key). Server-to-client frames **must not** be masked. This one-directional masking requirement was added to prevent cross-protocol attacks against transparent proxies.
- **Payload length**: 7 bits handles lengths 0-125 directly. If the value is 126, the next 2 bytes carry a 16-bit length. If 127, the next 8 bytes carry a 64-bit length. Variable-length encoding to keep small messages efficient.

### Ping/Pong Heartbeats

WebSocket defines ping (opcode `0x9`) and pong (opcode `0xA`) control frames for probing connection health:

- Either side can send a ping. The other side **must** respond with a pong containing the same payload.
- The payload is limited to 125 bytes.
- If a pong is not received within a timeout, the connection is considered dead.

Why not rely on TCP keep-alive? TCP keep-alive operates at the OS level with coarse timeouts — by default, 2 hours on Linux. WebSocket ping/pong operates at the application level with configurable granularity. For a real-time chat application, you want to detect dead connections within 30-60 seconds, not 2 hours. Sending a ping every 30 seconds and closing the connection if no pong arrives within 10 seconds is a common pattern.

This also interacts with the load balancer timeout problem (discussed below) — pings keep the connection active from the LB's perspective.

### Close Handshake

WebSocket connections close gracefully with their own close handshake:

1. Either side sends a close frame (opcode `0x8`) with an optional status code and human-readable reason string.
2. The recipient responds with its own close frame (acknowledging the close).
3. Both sides close the underlying TCP connection.

**Close status codes:**
- `1000`: Normal closure — the connection served its purpose.
- `1001`: Going away — server is shutting down, or the browser is navigating away from the page.
- `1006`: Abnormal closure — the connection was lost without a close frame. This code is generated locally and never actually sent over the wire; you see it when the TCP connection drops unexpectedly.
- `1008`: Policy violation — the server rejected the message content.
- `1009`: Message too big — the message exceeded the server's configured maximum.
- `1011`: Unexpected server error — the server encountered a condition that prevented it from fulfilling the request.

### When to Use WebSocket vs Alternatives

Not every real-time problem requires WebSocket. The right choice depends on the communication pattern:

| Feature | WebSocket | SSE (Server-Sent Events) | Long Polling | Short Polling |
|---------|-----------|--------------------------|--------------|---------------|
| Direction | Bidirectional | Server → Client only | Server → Client (with request per update) | Client → Server (periodic) |
| Connection | Persistent | Persistent | Held open, reconnects per message | New request each poll |
| Protocol | Custom binary frames | Plain HTTP (text/event-stream) | Plain HTTP | Plain HTTP |
| Browser support | Universal | Universal (except old IE) | Universal | Universal |
| Proxy/CDN friendly | Problematic | Yes (just HTTP) | Yes | Yes |
| Complexity | High | Low | Medium | Low |

**Use WebSocket when:**
- You need bidirectional real-time communication — chat, collaborative editing, multiplayer games where the server also needs to receive frequent messages from the client.
- You need very low latency (sub-100ms) server-to-client updates.
- You need high-frequency updates (more than once per second).

**Use SSE when:**
- You only need server-to-client streaming — live feeds, notifications, progress updates, AI text generation.
- You want automatic reconnection built in (SSE handles this; WebSocket does not).
- You need to work cleanly with existing HTTP infrastructure — CDNs, proxies, monitoring tools all handle SSE transparently.

**Use polling when:**
- Update frequency is low (every 30-60 seconds).
- Simplicity matters more than efficiency.
- You need to support environments where WebSocket or SSE might be blocked.

### Scaling WebSockets Horizontally

WebSocket connections are stateful — a client is persistently connected to a specific server process. This is the central challenge of WebSocket scaling. With a stateless HTTP API, you can route any request to any server. With WebSockets, you cannot.

**Problem**: You have 4 servers behind a load balancer. Client A is connected to Server 1. Client B is connected to Server 2. When Client B sends a message intended for Client A, it arrives at Server 2 — which has no connection to Client A.

```
Client A ←→ Server 1 ←→ Redis Pub/Sub ←→ Server 2 ←→ Client B
                              ↕
                          Server 3 ←→ Client C
```

**Solution 1 — Sticky sessions**: Route each client to the same server based on a cookie or IP hash. Simple, but creates single points of failure (Server 1 going down drops all its connections), causes uneven load as different servers accumulate different numbers of idle connections, and complicates zero-downtime deployments.

**Solution 2 — Pub/sub backbone**: All servers subscribe to a shared message bus (Redis Pub/Sub, NATS, Kafka). When any server needs to send a message to a client, it publishes to the bus with the client ID. Every server receives the message and delivers it to the client if that client is connected to it. This scales horizontally to arbitrary numbers of servers. Redis Pub/Sub is the standard choice for this pattern — it is low-latency and nearly zero configuration.

**Solution 3 — Dedicated WebSocket service**: Offload the stateful connection management to a specialized service. Ably, Pusher, and AWS API Gateway WebSocket handle the connection state; your backend just publishes messages via their API. This trades cost for operational simplicity and lets your backend remain stateless.

### Common WebSocket Issues

**Proxy/load balancer timeout on idle connections**: Many load balancers (AWS ALB, nginx) have idle timeouts. ALB's default is 60 seconds — if no data flows for 60 seconds, the LB terminates the connection. Your client sees an unexpected close with status 1006. Solution: send pings from the server at an interval shorter than the LB timeout.

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

**Reconnection strategy**: WebSocket does not auto-reconnect. When the connection drops, your client code must detect it and reconnect. Use exponential backoff with jitter — without jitter, all clients that were connected to a server that just restarted will reconnect simultaneously, potentially overloading it:

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

**Backpressure**: If the server sends messages faster than the client can process them, the TCP send buffer fills up. The server's `write()` calls start blocking or returning errors. The server should monitor the WebSocket's buffered amount and either throttle, queue, or drop messages for slow clients, rather than accumulating unbounded memory.

---

## 6. gRPC & Protocol Buffers

### Why Binary Protocols Are Worth Understanding

Most web services use JSON over HTTP. JSON is human-readable, universally supported, and easy to debug. For internal service-to-service communication at scale, though, JSON has real costs: parsing is slow, encoding is verbose, and there is no schema enforcement beyond documentation and convention.

gRPC, developed by Google and open-sourced in 2015, is what Google uses internally for the vast majority of its service-to-service communication. It combines Protocol Buffers (a binary serialization format with strict schemas) with HTTP/2 transport to deliver a highly efficient, strongly-typed RPC framework. Understanding both layers — the wire format and the transport — is what allows you to use gRPC effectively and debug it when things go wrong.

### Protobuf Wire Format

Protocol Buffers encode data as a sequence of (field_number, wire_type, value) tuples. There are no field names in the encoded output — only numbers. This is what makes protobuf compact, fast, and backward-compatible.

**Wire types:**

| Wire Type | Meaning | Used For |
|-----------|---------|----------|
| 0 | Varint | int32, int64, uint32, uint64, sint32, sint64, bool, enum |
| 1 | 64-bit | fixed64, sfixed64, double |
| 2 | Length-delimited | string, bytes, embedded messages, repeated fields (packed) |
| 5 | 32-bit | fixed32, sfixed32, float |

**Varint encoding** is one of the cleverest space-saving tricks in the format. Instead of always using 4 bytes for an integer, protobuf uses variable-length encoding: each byte uses 7 bits for data and 1 bit (the most significant bit) to indicate whether more bytes follow. The value `1` uses 1 byte. The value `300` uses 2 bytes. Large values use more bytes, but most integers in practice are small.

**Field numbers are permanent identities.** The `.proto` file assigns a number to each field. That number — not the field name — is what appears in the wire format. This is the foundation of protobuf's backward compatibility: old and new code can safely exchange messages because unrecognized field numbers are ignored, and missing field numbers use default values. It is also why field numbers must never be reused — reassigning a number to a different field causes silent data corruption.

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

Total: 12 bytes. JSON would encode `{"id":150,"name":"Alice"}` as 30 bytes — more than 2x larger, and that ignores the parsing overhead.

### gRPC over HTTP/2

gRPC uses HTTP/2 as its transport layer. Each RPC call maps to a single HTTP/2 stream — you get all of HTTP/2's multiplexing and header compression for free.

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

- The RPC method name becomes the HTTP path: `/package.ServiceName/MethodName`. This is what you see in logs and monitoring.
- Request and response bodies are protobuf-encoded, prefixed with a 5-byte header: 1 byte indicating whether the message is compressed, followed by 4 bytes for the message length.
- gRPC uses **HTTP trailers** — headers sent after the response body — to deliver the `grpc-status` code. The HTTP status code is always 200 (OK), even for gRPC errors. The actual success or failure signal is in the trailer. This surprises many people debugging gRPC with standard HTTP monitoring tools.

### gRPC Call Types

gRPC supports four call patterns, defined in the service definition:

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

**Unary**: The workhorse. One request, one response — the direct equivalent of a REST API call. Use this for most RPC operations.

**Server streaming**: The server sends multiple messages back over a single stream. Perfect for large datasets where you want to start processing before the full result is available, real-time feeds, or long-running operations that emit progress updates.

**Client streaming**: The client sends multiple messages and receives a single response. Useful for chunked file upload (send chunks, receive confirmation), batch operations, or aggregation (send many readings, receive a computed summary).

**Bidirectional streaming**: Both sides send independent streams of messages. The server does not wait for the client to finish, and vice versa. This is the gRPC equivalent of WebSocket — it enables true real-time bidirectional communication, like a chat system or a real-time collaborative protocol.

### gRPC Metadata

gRPC metadata is the RPC equivalent of HTTP headers: key-value pairs sent alongside RPCs. Metadata comes in two flavors:

- **Headers**: Sent before the first message. Used for authentication tokens, request IDs, distributed tracing context (W3C trace context, OpenTelemetry).
- **Trailers**: Sent after the last message. Contains `grpc-status` and `grpc-message`. Can carry custom metadata.

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

gRPC defines its own status codes, entirely separate from HTTP status codes:

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

**Retry policy**: Only `UNAVAILABLE` (14) should be retried automatically in most cases. `DEADLINE_EXCEEDED` (4) can be retried if and only if the operation is idempotent — retrying a non-idempotent operation that already succeeded (but timed out before the response arrived) causes double execution.

### gRPC Interceptors

Interceptors are gRPC's middleware pattern — the equivalent of HTTP middleware stacks. They wrap RPC calls to add cross-cutting concerns without polluting your business logic:

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

Common interceptor use cases: logging, metrics (Prometheus instrumentation), authentication (token validation), distributed tracing (OpenTelemetry span creation), rate limiting, panic recovery.

### gRPC-Web

Browsers cannot use native gRPC directly. The problem is that browsers expose HTTP/2 through the Fetch API, but they do not give JavaScript code control over individual HTTP/2 frames or trailing headers — both of which gRPC requires. **gRPC-Web** is a protocol adaptation that works around these limitations:

- Uses HTTP/1.1 or HTTP/2 in ways browsers support.
- Encodes trailers in the response body instead of using HTTP trailers (since browsers cannot access those).
- Requires a proxy (Envoy or grpc-web-proxy) between the browser and the gRPC server to translate.

```
Browser → [gRPC-Web request over HTTP/1.1] → Envoy proxy → [native gRPC over HTTP/2] → gRPC server
```

**Connect** (from Buf) is a newer alternative that provides gRPC compatibility without requiring a proxy. It uses standard HTTP POST with JSON or protobuf bodies — anything that can make an HTTP request can be a Connect client, including `curl`. This makes it significantly easier to work with from browsers and scripting environments.

### Protobuf Schema Evolution

One of protobuf's most valuable properties is that it is designed for backward and forward compatible schema changes. Old code can decode messages from new producers (ignoring unknown fields), and new code can decode messages from old producers (using defaults for missing fields). This allows independent deployment of services — you can deploy a new server before updating all clients.

**Safe changes:**
- **Add a new field** with a new field number. Old code ignores it (unknown fields pass through). New code uses the default value when reading old messages.
- **Remove a field** — but **reserve** its number so it can never be accidentally reused.
- **Rename a field** — field names are not in the wire format. Old and new code interoperate fine.

**Unsafe changes:**
- **Change a field number** — breaks all existing encoded data permanently.
- **Change a field type** (e.g., `int32` → `string`) — the decoder attempts to interpret the bytes as the new type. Results are garbled or panics.
- **Reuse a field number** — the most dangerous mistake. Old messages with data at that field number will be decoded as the new field type, causing silent corruption.

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

The `reserved` directive enforces this at compile time: the protobuf compiler will reject any attempt to define a new field with a reserved number or name.

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

**General rule**: Use gRPC for internal service-to-service communication where performance matters. Use REST for public APIs, browser-facing endpoints, and any situation where human debuggability matters. Many organizations use both: gRPC for the service mesh, REST (or GraphQL) for the external API.

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

**Bloom RPC** (now succeeded by **Kreya** and **Postman gRPC**): GUI tools for testing gRPC services, similar to Postman for REST. If you work with gRPC daily, a GUI tool pays for the setup time.

**grpc-web-devtools**: A Chrome extension that decodes gRPC-Web traffic in the DevTools Network tab, showing the decoded protobuf instead of binary blobs.

---

## 7. Network Debugging & Troubleshooting

### The 3 AM Toolkit

Production is down. Users are reporting failures. The monitoring dashboards are turning red. You have five minutes to figure out what is happening before your on-call escalates and you are explaining yourself to your director.

This section is organized around exactly that scenario. These are the tools, commands, and mental models that will get you from "something is broken" to "I know exactly what is broken" in the minimum time.

### curl — The Swiss Army Knife

curl is the single most important debugging tool for HTTP-based services. It is available everywhere, enormously capable, and it speaks HTTP in a way that exposes exactly what is happening at each layer.

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

The timing breakdown is the most powerful feature. Learn to read it:

```
DNS lookup:     0.012s     ← DNS resolution took 12ms
TCP connect:    0.045s     ← TCP handshake completed at 45ms (so TCP handshake = 45 - 12 = 33ms)
TLS handshake:  0.095s     ← TLS completed at 95ms (so TLS handshake = 95 - 45 = 50ms)
TTFB:           0.250s     ← First byte at 250ms (so server processing = 250 - 95 = 155ms)
Total:          0.260s     ← Done at 260ms (so transfer = 260 - 250 = 10ms)
```

Each layer tells you where to look:
- DNS is slow → check resolver, consider local caching.
- TCP connect is slow → network latency or packet loss; use `mtr`.
- TLS is slow → consider session resumption, check OCSP stapling, rule out CPU-bound crypto.
- TTFB minus TLS is large → server processing time is the problem (database, computation, upstream dependency).
- Total minus TTFB is large → response body is big or bandwidth is constrained; compress, paginate, reduce payload.

### tcpdump

tcpdump captures packets on a network interface. It is available on virtually every Linux/Unix system, requires no configuration, and works even when your application is completely broken. When curl shows you *what* is happening, tcpdump shows you *how*.

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

**Common tcpdump debugging patterns:**

```bash
# Are SYN packets being sent? (Is the client trying to connect?)
sudo tcpdump -i any 'tcp[tcpflags] == tcp-syn' and host api.example.com

# Are SYN-ACKs coming back? (Is the server responding?)
sudo tcpdump -i any 'tcp[tcpflags] == (tcp-syn|tcp-ack)' and host api.example.com

# Are there retransmissions? (Packet loss or congestion)
sudo tcpdump -i any tcp and host api.example.com | grep retransmit
# (Better: analyze in Wireshark which detects retransmissions automatically)
```

If you see SYN packets leaving but no SYN-ACK arriving, the problem is somewhere in the network — firewall, security group, the remote host. If you see SYN-ACK arriving but the connection never completes, something is wrong with the three-way handshake completion. If you see RST packets arriving, the remote side is actively rejecting the connection.

### Wireshark

Wireshark provides a GUI for deep packet analysis. While tcpdump captures, Wireshark analyzes. Save a tcpdump capture to a `.pcap` file on the server, copy it to your local machine, and open it in Wireshark for deep analysis.

**Capture filters** (BPF syntax, applied during capture — can only see matching packets):
```
host 10.0.1.50
port 443
tcp port 8080 and host 10.0.1.50
```

**Display filters** (applied after capture — far richer and more powerful):
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

**Following a TCP stream**: Right-click any packet → "Follow" → "TCP Stream." Wireshark reassembles the complete conversation — all data sent in both directions — in a readable format. This is invaluable for understanding what your application is actually sending and receiving, especially for debugging protocol issues.

**Expert Info**: Analyze → Expert Information shows a categorized summary of everything Wireshark found suspicious: retransmissions, duplicate ACKs, window-full events, RST packets. Start here when you have a capture and are not sure what you are looking for.

### mtr — Network Path Analysis

mtr combines traceroute and ping into a continuously-updating tool that shows latency and packet loss at every hop between you and your destination. When `curl` shows that TCP connect is slow, `mtr` tells you *where*.

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

**Interpreting the output:**

- **Loss% increasing at a hop and remaining high for all subsequent hops**: Real packet loss at that hop. The network between hop N-1 and hop N is dropping packets. This is the problem. Contact your network provider or cloud support.
- **Loss% at one hop but 0% at subsequent hops**: The router at that hop is deprioritizing ICMP traceroute packets (routing protocols like OSPF and BGP take priority). The router is healthy — traceroute just is not its job. Ignore this loss.
- **Large latency jump at a hop**: Expected when crossing a long network segment (trans-continental, trans-oceanic). Unexpected if two hops are supposedly in the same datacenter.

### ss / netstat

`ss` is the modern replacement for `netstat`. It reads from the kernel directly rather than parsing `/proc/net/tcp`, making it faster and more accurate.

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

**What to watch for:**

- **High TIME-WAIT count**: Too many short-lived connections. Implement connection pooling.
- **CLOSE-WAIT accumulation**: Your application is not closing connections after the remote side has sent FIN. This is a code bug — you are leaking file descriptors. Left unchecked, this will eventually exhaust the FD limit and crash the process.
- **SYN-SENT stuck**: Your outbound connection attempts are not getting responses. Firewall, security group, or the remote server is down.
- **Listen backlog overflow**: `ss -tlnp` shows the current backlog; if connections are being dropped silently, increase the backlog in your server configuration.

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

Use `dig +trace` when you want to see what the authoritative server is returning, independent of any caching layers. If `dig api.example.com` returns the wrong result but `dig +trace api.example.com` returns the right result, the problem is stale cache in a resolver. If `dig +trace` also returns the wrong result, the authoritative server is misconfigured.

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

When a request is slow, do not guess — systematically determine where the time is being spent:

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

**Symptoms**: Consistent 504 errors after exactly N seconds (the proxy's configured timeout).

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

**Symptoms**: "Connection refused" immediately (no timeout — this distinguishes it from a firewall drop, which times out silently).

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

Production is on fire. Here is the sequence:

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

The network is not a black box. It is a stack of well-specified protocols, each with documented behavior, observable state, and debuggable failure modes. Every production issue — slow requests, intermittent failures, mysterious timeouts, certificate errors — has a root cause in one of the layers covered in this chapter.

The mental model that unifies everything:

1. **DNS**: Is the name resolving correctly and quickly? `dig`, `dig +trace`.
2. **TCP**: Is the connection establishing, and is data flowing without loss? `ss`, `mtr`, `tcpdump`.
3. **TLS**: Is the handshake succeeding, and are certificates valid? `openssl s_client`, `curl -v`.
4. **HTTP**: Are the right headers set, and is the server returning the expected status? `curl`, Wireshark.
5. **Application**: Is the server processing the request efficiently? Application logs, profilers, distributed traces.

When debugging, work from the bottom up. Use `curl -w` to identify which layer is slow. Then use the layer-specific tools to pinpoint the cause. You will find most production issues fall into a small number of categories: DNS cache staleness, connection pool exhaustion, TLS certificate chain problems, or slow database queries masquerading as network issues.

The engineers who get paged at 3 AM and actually fix things — rather than rebooting servers and hoping — are the ones who understand these layers. They know that `CLOSE_WAIT` means their code has a bug, that a `502` points upstream, that `TIME_WAIT` is a symptom of missing connection pooling, and that TLS handshake time is the fingerprint of OCSP lookups and certificate chain length.

Now you know it too.

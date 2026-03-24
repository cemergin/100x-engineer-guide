<!--
  CHAPTER: A
  TITLE: Engineering Glossary
  PART: V — Appendices
  PREREQS: None (reference)
  KEY_TOPICS: 250+ engineering terms, abbreviations, slang, organized by domain
  DIFFICULTY: All levels
  UPDATED: 2026-03-24
-->

# Appendix A: Engineering Glossary

> **Part V — Appendices** | Prerequisites: None (reference) | Difficulty: All levels

A comprehensive dictionary of 250+ engineering terms, abbreviations, and culture phrases — from ACID to ZGC, from bikeshedding to yak shaving. The reference you bookmark and search constantly.

### In This Chapter
- Architecture & Design
- Reliability & Operations
- Distributed Systems
- Networking & Protocols
- DevOps & Infrastructure
- Security
- Data & Databases
- Performance
- Concurrency
- Testing
- AI/ML Engineering
- Cloud & AWS Specific
- Metrics & Processes
- Slang & Culture

### Related Chapters
- All chapters (terms are used throughout the guide)

---

## Architecture & Design

**ACID** — Atomicity, Consistency, Isolation, Durability. The four guarantees a database transaction must satisfy. Encountered whenever you discuss relational database reliability or compare SQL vs NoSQL tradeoffs.

**Aggregate** — A cluster of domain objects treated as a single unit for data changes. Central concept in Domain-Driven Design; the aggregate root is the only entry point for modifications.

**Anti-Corruption Layer** (ACL) — A translation layer that prevents one system's model from leaking into another. Used when integrating with legacy systems or third-party APIs whose data model you don't control.

**API** (Application Programming Interface) — A contract defining how software components communicate. You encounter APIs everywhere: REST endpoints, library methods, OS system calls.

**BFF** (Backend for Frontend) — A dedicated backend service tailored to a specific frontend (mobile, web, etc.). Avoids bloating a single API with every client's unique needs.

**Bounded Context** — A boundary within which a particular domain model is defined and applicable. Core DDD concept; different bounded contexts can use the same word to mean different things.

**Causal Consistency** — A consistency model guaranteeing that causally related operations are seen in the correct order by all nodes. Weaker than linearizability but stronger than eventual consistency.

**Clean Architecture** — An architecture pattern (by Robert C. Martin) organizing code in concentric layers with dependencies pointing inward. Business logic sits at the center, free of framework dependencies.

**CQRS** (Command Query Responsibility Segregation) — Separating read and write models into distinct paths. Common in event-sourced systems where the read side is a projection optimized for queries.

**CRDTs** (Conflict-Free Replicated Data Types) — Data structures that can be replicated across nodes and merged automatically without coordination. Used in collaborative editors, distributed caches, and offline-first apps.

**DDD** (Domain-Driven Design) — A software design approach centering the codebase around the business domain model. Introduces concepts like aggregates, entities, value objects, and ubiquitous language.

**Domain Event** — A record of something that happened in the domain that domain experts care about. Used in event-driven and event-sourced architectures to communicate state changes.

**EDA** (Event-Driven Architecture) — An architecture pattern where components communicate via events rather than direct calls. Enables loose coupling and asynchronous processing at scale.

**ELT** (Extract, Load, Transform) — A data pipeline pattern loading raw data into a target system before transforming it there. Preferred in modern data warehouses (Snowflake, BigQuery) where compute is cheap.

**Entity** — A domain object defined by its identity rather than its attributes. Two entities with the same data but different IDs are different; contrasts with Value Objects.

**ERD** (Entity-Relationship Diagram) — A visual representation of database entities and their relationships. Created during database design, often in tools like dbdiagram.io or Lucidchart.

**ESB** (Enterprise Service Bus) — Middleware that routes messages between services in a SOA architecture. Considered an anti-pattern by many modern architects due to centralized coupling.

**ETL** (Extract, Transform, Load) — A data pipeline pattern where data is extracted, transformed in transit, then loaded into the target. Traditional approach used in data warehousing.

**Event Sourcing** — Storing state as a sequence of events rather than current values. Instead of updating a row, you append an event. Enables full audit trails and temporal queries.

**Eventual Consistency** — A consistency model where all replicas converge to the same state given enough time. Standard in distributed systems (DynamoDB, Cassandra) trading consistency for availability.

**Fan-in** — A messaging pattern where multiple sources send messages to a single destination. Used in aggregation scenarios like collecting results from parallel workers.

**Fan-out** — A messaging pattern where a single message is delivered to multiple consumers. SNS topics and event buses use fan-out to distribute events to many subscribers.

**GraphQL** — A query language for APIs letting clients request exactly the data they need. Alternative to REST; eliminates over-fetching but introduces complexity in caching and authorization.

**gRPC** — A high-performance RPC framework using HTTP/2 and Protocol Buffers. Preferred for service-to-service communication where latency and type safety matter.

**HATEOAS** (Hypermedia as the Engine of Application State) — A REST constraint where responses include links to related actions. Rarely implemented fully in practice, but a key part of REST maturity.

**Hexagonal Architecture** (Ports and Adapters) — An architecture isolating business logic from external concerns via ports (interfaces) and adapters (implementations). Makes the core testable without infrastructure.

**Idempotency** — The property where performing an operation multiple times produces the same result as performing it once. Critical for retry logic, payment processing, and distributed messaging.

**Linearizability** — The strongest consistency model: every operation appears to take effect instantaneously at some point between invocation and response. Expensive to achieve in distributed systems.

**Microservices** — An architectural style decomposing an application into small, independently deployable services. Each service owns its data and communicates over the network.

**Monolith** — A single deployable unit containing all application functionality. Not inherently bad; simpler to develop, test, and deploy until scale or team size demands decomposition.

**MVC** (Model-View-Controller) — A UI architecture separating data (Model), presentation (View), and logic (Controller). Foundational pattern in web frameworks like Rails, Django, and Spring MVC.

**MVP** (Model-View-Presenter) — A variation of MVC where the Presenter handles UI logic and the View is passive. Common in Android development before MVVM took over.

**MVVM** (Model-View-ViewModel) — A UI pattern where the ViewModel exposes data and commands the View binds to. Standard in SwiftUI, Jetpack Compose, and WPF.

**ORM** (Object-Relational Mapping) — A library mapping database rows to programming language objects. Examples: Prisma, SQLAlchemy, Hibernate. Useful until you need complex queries.

**Outbox Pattern** — A reliability pattern storing events in a database table alongside business data, then publishing them asynchronously. Guarantees at-least-once delivery without distributed transactions.

**Protobuf** (Protocol Buffers) — Google's binary serialization format. Smaller and faster than JSON; used with gRPC and for efficient data storage.

**Pub/Sub** (Publish/Subscribe) — A messaging pattern where publishers emit events without knowing who consumes them. Decouples producers from consumers; implemented by Kafka, SNS, Google Pub/Sub.

**REST** (Representational State Transfer) — An architectural style for APIs using HTTP methods (GET, POST, PUT, DELETE) on resources. The dominant web API paradigm.

**RPC** (Remote Procedure Call) — A protocol allowing a program to execute a procedure on a remote server as if it were local. gRPC is the modern incarnation.

**Saga Pattern** — A pattern for managing distributed transactions as a sequence of local transactions with compensating actions for rollback. Used when you can't do a single ACID transaction across services.

**Serverless** — A cloud execution model where the provider manages infrastructure and scales automatically. You write functions (Lambda, Cloud Functions) and pay per invocation.

**SOA** (Service-Oriented Architecture) — An architectural style organizing software as coarse-grained services communicating over a network. Predecessor to microservices, often associated with ESBs.

**Strangler Fig** — A migration pattern incrementally replacing a legacy system by routing new functionality to new code while gradually migrating old features. Named after the strangler fig tree.

**Strong Consistency** — A guarantee that any read returns the most recent write. Simpler to reason about but harder to achieve in distributed systems.

**Ubiquitous Language** — A shared vocabulary between developers and domain experts used in code, conversations, and documentation. DDD concept that reduces translation errors.

**Value Object** — A domain object defined by its attributes, not identity. Two value objects with the same data are equal. Examples: Money, DateRange, Address.

**Vertical Slice** — An architecture organizing code by feature rather than by technical layer. Each slice contains its own controller, handler, and data access, reducing cross-cutting dependencies.

---

## Reliability & Operations

**Active-Active** — A deployment topology where multiple instances handle traffic simultaneously. Provides high availability and load distribution but requires conflict resolution for writes.

**Active-Passive** — A deployment topology where one instance handles traffic while a standby waits to take over on failure. Simpler than active-active but wastes standby resources.

**Backpressure** — A mechanism where a downstream component signals upstream to slow down when overwhelmed. Prevents cascading failures in streaming and message-driven systems.

**Blast Radius** — The scope of impact when something fails. Reducing blast radius (via cell architectures, feature flags, canary deploys) limits how many users a failure affects.

**Blue-Green Deployment** — A release strategy running two identical environments; traffic switches from blue (current) to green (new) atomically. Enables instant rollback.

**Bulkhead** — An isolation pattern preventing a failure in one component from cascading to others. Named after ship bulkheads; implemented via separate thread pools, connection pools, or services.

**Canary Deployment** — Routing a small percentage of traffic to a new version before full rollout. If metrics degrade, roll back without affecting most users.

**Chaos Engineering** — The discipline of intentionally injecting failures to discover system weaknesses. Pioneered by Netflix (Chaos Monkey); now a standard SRE practice.

**Circuit Breaker** — A pattern that stops calling a failing service after a threshold, allowing it to recover. Like an electrical circuit breaker: trips open, waits, then tests (half-open).

**Cold Standby** — A disaster recovery setup where the standby environment is not running and must be provisioned from backups. Cheapest but slowest recovery.

**Dark Launch** — Deploying a feature to production without exposing it to users, often to test backend behavior under real traffic. The feature flag is off for the UI but on for the backend.

**Error Budget** — The allowed amount of unreliability (100% minus SLO). If your SLO is 99.9%, your error budget is 0.1% downtime. Spend it on feature velocity; conserve it when low.

**Failback** — The process of returning to the primary system after a failover event. Often requires careful data synchronization to avoid data loss.

**Failover** — Automatically switching to a redundant system when the primary fails. Database failover, DNS failover, and load balancer health checks all enable this.

**Feature Flag** (Feature Toggle) — A mechanism to enable or disable features at runtime without deploying new code. Essential for canary releases, A/B testing, and kill switches.

**Fencing** — A mechanism preventing a node from acting on stale authority (e.g., a leader that doesn't know it's been replaced). Fencing tokens and STONITH are common techniques.

**Game Day** — A scheduled chaos engineering exercise simulating failures in a controlled environment. Teams practice incident response before real incidents happen.

**Graceful Degradation** — A design principle where a system continues operating with reduced functionality when components fail. Example: serving cached content when the database is down.

**Hot Standby** — A standby system that runs continuously and receives real-time data replication. Can take over almost immediately on failure.

**Incident Commander** (IC) — The person leading incident response, making decisions and coordinating communication. Defined in ICS (Incident Command System) methodology.

**Load Shedding** — Intentionally dropping excess traffic to protect system stability. Better to serve 80% of requests successfully than 100% poorly.

**MTBF** (Mean Time Between Failures) — The average time a system operates between failures. A reliability metric; higher is better.

**MTTD** (Mean Time to Detect) — The average time to detect an incident after it begins. Improved with better monitoring, alerting, and observability.

**MTTF** (Mean Time to Failure) — The average time until the first failure of a non-repairable system. Used for hardware and components that are replaced rather than repaired.

**MTTR** (Mean Time to Recovery) — The average time to restore service after a failure. One of the four DORA metrics; lower is better. Improved by runbooks, automation, and practice.

**On-call** — The practice of having engineers available to respond to production incidents outside business hours. Rotation schedules, escalation policies, and runbooks make it sustainable.

**Postmortem** (Post-Incident Review) — A structured analysis after an incident examining what happened, why, and how to prevent recurrence. Should be blameless and focused on systemic improvements.

**Rolling Update** — A deployment strategy updating instances one at a time, maintaining availability throughout. Slower than blue-green but uses fewer resources.

**RPO** (Recovery Point Objective) — The maximum acceptable data loss measured in time. An RPO of 1 hour means you can lose up to 1 hour of data.

**RTO** (Recovery Time Objective) — The maximum acceptable downtime after a failure. An RTO of 15 minutes means service must be restored within 15 minutes.

**Runbook** — A documented procedure for handling operational tasks or incidents. Ranges from simple checklists to automated scripts. Every alert should link to a runbook.

**SLA** (Service-Level Agreement) — A contract between a service provider and customer defining expected service levels and consequences for missing them. The business/legal wrapper around SLOs.

**SLI** (Service-Level Indicator) — A quantitative measure of a service's behavior (e.g., request latency, error rate). The raw metric that feeds into SLOs.

**SLO** (Service-Level Objective) — A target value for an SLI (e.g., 99.9% of requests < 200ms). The internal goal that should be stricter than the SLA.

**Split-Brain** — A failure mode where network partitions cause multiple nodes to believe they are the leader. Can cause data corruption; prevented by fencing and quorum.

**SRE** (Site Reliability Engineering) — A discipline applying software engineering to operations problems. Originated at Google; focuses on SLOs, error budgets, automation, and eliminating toil.

**Toil** — Repetitive, manual, automatable operational work that scales with the system. SRE's goal is to keep toil below 50% of an engineer's time.

**Traffic Mirroring** (Shadow Traffic) — Copying production traffic to a test environment for validation without affecting users. Useful for testing new services with real traffic patterns.

**War Room** — A dedicated space (physical or virtual) where teams collaborate during a major incident. Focused, synchronous communication to resolve critical issues quickly.

**Warm Standby** — A standby environment running at reduced capacity, receiving data replication. Can scale up and take over faster than cold standby but slower than hot.

---

## Distributed Systems

**2PC** (Two-Phase Commit) — A distributed transaction protocol with a prepare phase and a commit phase. Provides atomicity across nodes but blocks if the coordinator fails.

**3PC** (Three-Phase Commit) — An extension of 2PC adding a pre-commit phase to reduce blocking. Rarely used in practice due to complexity and network partition issues.

**Anti-Entropy** — A process where nodes periodically compare and reconcile their data to ensure consistency. Used in systems like Cassandra and Dynamo.

**B-Tree** — A self-balancing tree data structure optimized for disk reads, used in most relational database indexes. Provides O(log n) lookups with high fanout.

**Bloom Filter** — A space-efficient probabilistic data structure that tests set membership. Can produce false positives but never false negatives. Used in databases to avoid unnecessary disk reads.

**Byzantine Fault** — A failure where a node behaves arbitrarily (including maliciously), sending conflicting information to different peers. Byzantine fault tolerance is critical in blockchain systems.

**CAP Theorem** — States that a distributed system can provide at most two of three guarantees: Consistency, Availability, Partition tolerance. Since network partitions are inevitable, the real choice is C vs A during a partition.

**Compaction** — The process of merging and cleaning up storage files (SSTables in LSM trees, log segments in Kafka). Reclaims space and improves read performance.

**Consensus** — The process of getting distributed nodes to agree on a value. Solved by algorithms like Paxos and Raft; foundational to leader election, distributed locks, and replicated state machines.

**Consistent Hashing** — A hashing technique where adding or removing nodes only remaps a fraction of keys. Used in distributed caches (Memcached), databases (Cassandra), and load balancers.

**Gossip Protocol** — A communication protocol where nodes periodically exchange state with random peers. Information spreads epidemically; used for membership, failure detection, and metadata propagation.

**Heartbeat** — A periodic signal sent between nodes to indicate liveness. Missed heartbeats trigger failure detection and potentially leader election.

**Lamport Clock** — A logical clock providing a partial ordering of events in a distributed system. If event A happens before B, the Lamport timestamp of A is less than B's.

**Leader Election** — The process of designating one node as the coordinator among a group. Implemented via Raft, ZooKeeper, or etcd; critical for consensus and write coordination.

**LSM Tree** (Log-Structured Merge Tree) — A data structure optimizing write throughput by buffering writes in memory then flushing sorted runs to disk. Used in Cassandra, RocksDB, LevelDB.

**Merkle Tree** — A hash tree where each leaf is a hash of data and each parent is a hash of its children. Used for efficient data integrity verification and anti-entropy repair.

**PACELC** — An extension of CAP: if there's a Partition, choose Availability or Consistency; Else, choose Latency or Consistency. More nuanced than CAP for real-world system design.

**Partition** — A split in a distributed system, either intentional (data partitioning/sharding) or unintentional (network partition). Network partitions are the P in CAP theorem.

**Paxos** — A consensus algorithm proving that distributed agreement is possible despite failures. Famously difficult to understand and implement; often replaced by Raft.

**Quorum** — The minimum number of nodes that must agree for an operation to succeed. Typically a majority (n/2 + 1). Read quorum + write quorum > total nodes ensures consistency.

**Raft** — A consensus algorithm designed to be more understandable than Paxos. Used in etcd, CockroachDB, and TiKV. Splits consensus into leader election, log replication, and safety.

**Replication** — Copying data across multiple nodes for fault tolerance and read scalability. Strategies include synchronous, asynchronous, single-leader, multi-leader, and leaderless.

**Shard** (Sharding) — Horizontally partitioning data across multiple databases or nodes. Each shard holds a subset of the data; enables horizontal scaling but complicates joins and transactions.

**Split-Brain** — See Reliability & Operations section. A critical failure mode in distributed systems causing dual-leader scenarios.

**SSTable** (Sorted String Table) — An immutable, sorted file of key-value pairs written by LSM trees. Enables efficient range scans and merging during compaction.

**Tombstone** — A marker indicating a deleted record in an eventually consistent system. Necessary because you can't distinguish "deleted" from "not yet replicated" without it.

**Vector Clock** — A logical clock assigning a vector of counters to each event, enabling detection of causal relationships and concurrent updates. Used in Amazon Dynamo and Riak.

**WAL** (Write-Ahead Log) — A log where changes are written before being applied to the main data structure. Ensures durability and crash recovery in databases and message brokers.

---

## Networking & Protocols

**AMQP** (Advanced Message Queuing Protocol) — A messaging protocol supporting queuing, routing, and pub/sub. Implemented by RabbitMQ; used for reliable inter-service messaging.

**API Gateway** — A single entry point for API requests that handles routing, authentication, rate limiting, and transformation. Examples: AWS API Gateway, Kong, Apigee.

**CDN** (Content Delivery Network) — A globally distributed network of servers caching content close to users. CloudFront, Cloudflare, Fastly reduce latency for static and dynamic content.

**CIDR** (Classless Inter-Domain Routing) — A notation for IP address ranges (e.g., 10.0.0.0/16). Essential for VPC design, subnet planning, and security group rules.

**CORS** (Cross-Origin Resource Sharing) — A browser security mechanism controlling which domains can make requests to your API. The bane of frontend developers everywhere.

**CSP** (Content Security Policy) — An HTTP header restricting which resources a page can load. Mitigates XSS by whitelisting allowed script sources, image sources, etc.

**DNS** (Domain Name System) — The internet's phone book, translating domain names to IP addresses. Understanding DNS propagation, TTLs, and record types (A, CNAME, MX) is fundamental.

**Egress** — Outbound network traffic leaving a system or network boundary. Cloud providers often charge for egress; a significant cost factor in architecture decisions.

**Forward Proxy** — A proxy that sits between clients and the internet, forwarding client requests. Used for caching, filtering, and anonymity. Contrast with reverse proxy.

**gRPC** — See Architecture & Design. Used extensively in service-to-service networking.

**GraphQL** — See Architecture & Design. A networking/API concern as much as an architectural one.

**HTTP/2** — A major revision of HTTP adding multiplexing, header compression, and server push over a single TCP connection. Default in modern browsers and web servers.

**HTTP/3** — The latest HTTP version using QUIC (UDP-based) instead of TCP. Eliminates head-of-line blocking and improves performance on unreliable networks.

**Ingress** — Inbound network traffic entering a system or network boundary. In Kubernetes, an Ingress resource routes external HTTP traffic to services.

**L4** (Layer 4) — Transport layer in the OSI model (TCP/UDP). L4 load balancers route based on IP and port without inspecting application-level content.

**L7** (Layer 7) — Application layer in the OSI model (HTTP/HTTPS). L7 load balancers can route based on URL paths, headers, cookies, and content.

**Load Balancer** — A component distributing traffic across multiple backend instances. Can operate at L4 (NLB) or L7 (ALB). Essential for scalability and availability.

**MQTT** (Message Queuing Telemetry Transport) — A lightweight pub/sub messaging protocol designed for IoT and constrained networks. Low bandwidth, supports QoS levels.

**mTLS** (Mutual TLS) — TLS where both client and server authenticate each other with certificates. Standard in service meshes and zero-trust architectures.

**NAT** (Network Address Translation) — Translating private IP addresses to public ones for internet access. NAT Gateways enable private subnet instances to reach the internet without being publicly accessible.

**QUIC** — A UDP-based transport protocol developed by Google, forming the basis of HTTP/3. Provides built-in encryption, multiplexing, and faster connection establishment.

**REST** — See Architecture & Design. The dominant API networking paradigm.

**Reverse Proxy** — A proxy sitting in front of servers, forwarding client requests to backends. Nginx, HAProxy, and Envoy are common examples; handles SSL termination, caching, and load balancing.

**Service Mesh** — An infrastructure layer handling service-to-service communication with features like mTLS, observability, and traffic management. Istio and Linkerd are popular implementations.

**Sidecar** — A container running alongside the main application container in the same pod, providing cross-cutting functionality (logging, proxying, security). Central to the service mesh pattern.

**SSE** (Server-Sent Events) — A protocol for one-way server-to-client streaming over HTTP. Simpler than WebSockets when you only need server push (e.g., live feeds, notifications).

**SSL** (Secure Sockets Layer) — The predecessor to TLS for encrypted communication. Technically deprecated, but "SSL" is still colloquially used to mean TLS.

**Subnet** — A logical subdivision of an IP network. In cloud architectures, subnets define public (internet-facing) and private (internal-only) network segments within a VPC.

**TCP** (Transmission Control Protocol) — A reliable, ordered, connection-oriented transport protocol. The backbone of HTTP, databases, and most internet communication.

**TLS** (Transport Layer Security) — A cryptographic protocol providing encrypted communication over a network. Powers HTTPS; current version is TLS 1.3.

**UDP** (User Datagram Protocol) — A connectionless transport protocol with no delivery guarantees. Used where speed matters more than reliability: gaming, DNS, video streaming, QUIC.

**VPC** (Virtual Private Cloud) — An isolated virtual network in a cloud provider. You define subnets, route tables, and security groups to control network topology and access.

**WebRTC** (Web Real-Time Communication) — A protocol for peer-to-peer audio, video, and data communication in browsers. Used in video conferencing, screen sharing, and real-time collaboration.

**WebSocket** — A protocol providing full-duplex communication over a single TCP connection. Used for real-time features: chat, live updates, collaborative editing.

---

## DevOps & Infrastructure

**AMI** (Amazon Machine Image) — A template containing the software configuration for launching EC2 instances. Pre-baked AMIs speed up instance startup and ensure consistency.

**ArgoCD** — A GitOps continuous delivery tool for Kubernetes. Watches a Git repo and syncs the cluster state to match declared manifests.

**CDK** (Cloud Development Kit) — An AWS framework for defining infrastructure using programming languages (TypeScript, Python, etc.) instead of YAML/JSON. Compiles to CloudFormation.

**CD** (Continuous Delivery/Deployment) — Continuous Delivery: every commit is releasable. Continuous Deployment: every commit is automatically released. The difference is a manual approval gate.

**CI** (Continuous Integration) — The practice of frequently merging code changes and automatically building/testing them. Catches integration issues early; implemented by GitHub Actions, Jenkins, CircleCI.

**ConfigMap** — A Kubernetes object storing non-sensitive configuration as key-value pairs. Mounted as environment variables or files in pods. Use Secrets for sensitive data.

**Container** — A lightweight, isolated runtime environment sharing the host OS kernel. Docker is the most common container runtime; OCI defines the standard.

**CRD** (Custom Resource Definition) — A Kubernetes extension mechanism defining new resource types. Enables operators to manage custom workloads (databases, message brokers) natively in K8s.

**DaemonSet** — A Kubernetes resource ensuring a pod runs on every node (or a subset). Used for node-level concerns like log collectors, monitoring agents, and storage drivers.

**Deployment** — A Kubernetes resource managing stateless application rollouts with declarative updates, scaling, and rollback. The most common way to run workloads in K8s.

**Envoy** — A high-performance L7 proxy used as the data plane in service meshes (Istio). Handles load balancing, observability, and traffic management.

**Flux** — A GitOps toolkit for Kubernetes that keeps clusters in sync with Git repositories. Alternative to ArgoCD for continuous delivery.

**GitOps** — An operational model using Git as the single source of truth for infrastructure and application configuration. Changes are made via pull requests; reconciliation is automated.

**Helm** — A package manager for Kubernetes using templated YAML charts. Simplifies deploying complex applications but can lead to template sprawl.

**HPA** (Horizontal Pod Autoscaler) — A Kubernetes resource automatically scaling pod replicas based on CPU, memory, or custom metrics. Essential for handling variable traffic.

**Hypervisor** — Software creating and managing virtual machines (VMs). Type 1 (bare metal): ESXi, KVM. Type 2 (hosted): VirtualBox, VMware Workstation.

**IaC** (Infrastructure as Code) — Managing infrastructure through code rather than manual processes. Terraform, Pulumi, CloudFormation, and CDK are popular tools.

**Ingress Controller** — A Kubernetes component implementing Ingress resources by configuring a load balancer (Nginx, Traefik, ALB). Routes external traffic to internal services.

**Istio** — A service mesh platform providing traffic management, security (mTLS), and observability for Kubernetes. Powerful but complex; consider Linkerd as a simpler alternative.

**Kustomize** — A Kubernetes configuration management tool using overlays and patches rather than templates. Built into kubectl; simpler than Helm for basic customization.

**Linkerd** — A lightweight service mesh for Kubernetes focused on simplicity and performance. Easier to operate than Istio with lower resource overhead.

**Namespace** — A Kubernetes mechanism for logically partitioning a cluster. Used to separate environments (dev, staging, prod) or teams within a shared cluster.

**Node** — A worker machine in a Kubernetes cluster running pods. Can be a physical server or VM; managed by the control plane.

**Operator** — A Kubernetes pattern using CRDs and custom controllers to automate application lifecycle management. Encodes operational knowledge as software.

**Pod** — The smallest deployable unit in Kubernetes; one or more containers sharing network and storage. Most pods run a single application container.

**Pulumi** — An IaC tool using general-purpose programming languages (TypeScript, Python, Go). Alternative to Terraform with full language features instead of HCL.

**PVC** (Persistent Volume Claim) — A Kubernetes request for storage. Abstracts the underlying storage provider, enabling pods to use persistent disks portably.

**Secret** — A Kubernetes object storing sensitive data (passwords, tokens, keys). Base64-encoded by default; should be encrypted at rest and managed via external secret managers.

**StatefulSet** — A Kubernetes resource for stateful applications providing stable network identities, persistent storage, and ordered deployment. Used for databases and distributed systems.

**Terraform** — HashiCorp's IaC tool using HCL (HashiCorp Configuration Language) to define infrastructure across cloud providers. The most widely adopted multi-cloud IaC tool.

**VM** (Virtual Machine) — An emulation of a computer system providing the functionality of a physical computer. Heavier than containers but provides stronger isolation.

**VPA** (Vertical Pod Autoscaler) — A Kubernetes component that automatically adjusts pod CPU and memory requests based on usage. Complements HPA for right-sizing resources.

---

## Security

**2FA** (Two-Factor Authentication) — Authentication requiring two different factors (something you know + something you have). A subset of MFA; typically password + TOTP code.

**ABAC** (Attribute-Based Access Control) — An authorization model evaluating attributes (user role, resource type, time of day) against policies. More flexible than RBAC but harder to audit.

**CORS** — See Networking & Protocols. A security mechanism as much as a networking concern.

**CSRF** (Cross-Site Request Forgery) — An attack tricking a user's browser into making unwanted requests to a site where they're authenticated. Prevented with CSRF tokens and SameSite cookies.

**CSP** — See Networking & Protocols. A security header preventing content injection attacks.

**CVE** (Common Vulnerabilities and Exposures) — A standardized identifier for publicly known security vulnerabilities (e.g., CVE-2021-44228 for Log4Shell). Track CVEs in your dependencies.

**DAST** (Dynamic Application Security Testing) — Security testing of a running application by simulating attacks. Tools like OWASP ZAP and Burp Suite probe live endpoints.

**DDoS** (Distributed Denial of Service) — An attack flooding a system with traffic from many sources to make it unavailable. Mitigated by WAFs, CDNs, and rate limiting.

**Envelope Encryption** — A pattern where data is encrypted with a data key, and the data key is encrypted with a master key. Used by AWS KMS; limits exposure if a single key is compromised.

**HSM** (Hardware Security Module) — A physical device for managing and safeguarding cryptographic keys. AWS CloudHSM provides dedicated HSMs; KMS uses shared HSMs.

**HSTS** (HTTP Strict Transport Security) — An HTTP header instructing browsers to only connect via HTTPS. Prevents protocol downgrade attacks and cookie hijacking.

**IDOR** (Insecure Direct Object Reference) — A vulnerability where an attacker accesses resources by manipulating identifiers (e.g., changing `/users/123` to `/users/124`). Prevented by proper authorization checks.

**JWT** (JSON Web Token) — A compact, URL-safe token format for transmitting claims between parties. Commonly used for stateless authentication; consists of header, payload, and signature.

**KMS** (Key Management Service) — A managed service for creating and controlling encryption keys. AWS KMS, GCP Cloud KMS, and Azure Key Vault are cloud-native options.

**MFA** (Multi-Factor Authentication) — Authentication requiring multiple verification factors (knowledge, possession, biometrics). The single most impactful security control for user accounts.

**mTLS** — See Networking & Protocols. A critical security mechanism for service-to-service authentication.

**OAuth** (Open Authorization) — An authorization framework enabling third-party applications to access resources on behalf of a user without sharing credentials. OAuth 2.0 is the current standard.

**OIDC** (OpenID Connect) — An identity layer on top of OAuth 2.0 providing authentication (who you are) in addition to authorization (what you can access). Issues ID tokens with user claims.

**OWASP** (Open Web Application Security Project) — A nonprofit producing security standards, tools, and documentation. The OWASP Top 10 is the most referenced list of web application vulnerabilities.

**Principle of Least Privilege** — Granting only the minimum permissions necessary for a task. Foundational security principle; applies to IAM roles, database users, and service accounts.

**RBAC** (Role-Based Access Control) — An authorization model assigning permissions to roles, then roles to users. Simpler than ABAC; the most common authorization model in practice.

**ReBAC** (Relationship-Based Access Control) — An authorization model based on relationships between entities (e.g., "user X is a member of org Y"). Used by Google Zanzibar and AuthZed.

**SAML** (Security Assertion Markup Language) — An XML-based standard for exchanging authentication and authorization data between an identity provider and service provider. Common in enterprise SSO.

**SAST** (Static Application Security Testing) — Analyzing source code for security vulnerabilities without executing it. Tools like Semgrep, SonarQube, and CodeQL scan during CI.

**SBOM** (Software Bill of Materials) — A formal inventory of all components, libraries, and dependencies in a software artifact. Increasingly required for supply chain security compliance.

**SCA** (Software Composition Analysis) — Identifying known vulnerabilities in open-source dependencies. Tools like Snyk, Dependabot, and Trivy scan your dependency tree.

**SQLi** (SQL Injection) — An attack inserting malicious SQL into queries via unsanitized input. Prevented by parameterized queries/prepared statements. Still the most common web vulnerability.

**SSRF** (Server-Side Request Forgery) — An attack where the server is tricked into making requests to unintended destinations (internal services, metadata endpoints). Mitigated by URL validation and network controls.

**WAF** (Web Application Firewall) — A firewall filtering HTTP traffic based on rules to protect against XSS, SQLi, and other web attacks. AWS WAF, Cloudflare WAF, and ModSecurity are examples.

**XSS** (Cross-Site Scripting) — An attack injecting malicious scripts into web pages viewed by other users. Types: stored, reflected, DOM-based. Prevented by output encoding and CSP.

**Zero Trust** — A security model assuming no implicit trust; every request is verified regardless of network location. "Never trust, always verify." Implemented via mTLS, identity-aware proxies, and micro-segmentation.

---

## Data & Databases

**ACID** — See Architecture & Design. The foundational guarantees of relational database transactions.

**BASE** (Basically Available, Soft state, Eventually consistent) — A consistency model for NoSQL databases trading strong consistency for availability. The alternative philosophy to ACID.

**CAP** — See Distributed Systems (CAP Theorem). The fundamental constraint governing distributed database design.

**CDC** (Change Data Capture) — Tracking and capturing changes in a database as they occur. Used for replication, event sourcing, and keeping derived data stores in sync. Tools: Debezium, DMS.

**Connection Pool** — A cache of reusable database connections avoiding the overhead of creating new connections per request. PgBouncer, HikariCP, and Prisma's pool are common implementations.

**CTE** (Common Table Expression) — A named temporary result set within a SQL query (WITH clause). Improves readability and enables recursive queries.

**Data Lake** — A centralized repository storing raw data in its native format at any scale. Typically built on S3 or HDFS; schema-on-read rather than schema-on-write.

**Data Lakehouse** — An architecture combining data lake storage with data warehouse management features. Databricks, Delta Lake, and Apache Iceberg enable this pattern.

**Data Mesh** — A decentralized data architecture treating data as a product owned by domain teams. Contrasts with centralized data lake/warehouse approaches.

**Data Vault** — A data modeling methodology for data warehouses using hubs (entities), links (relationships), and satellites (attributes). Designed for auditability and flexibility.

**dbt** (data build tool) — A transformation tool that lets analysts write SQL SELECT statements that dbt materializes into tables and views. The standard for modern analytics engineering.

**DCL** (Data Control Language) — SQL commands controlling access permissions: GRANT, REVOKE. Defines who can do what to which database objects.

**DDL** (Data Definition Language) — SQL commands defining database structure: CREATE, ALTER, DROP. Changes the schema rather than the data.

**Denormalization** — Intentionally adding redundant data to improve read performance at the cost of write complexity. Common in NoSQL and read-heavy workloads.

**DML** (Data Manipulation Language) — SQL commands modifying data: INSERT, UPDATE, DELETE, SELECT. The everyday queries that interact with data.

**Index** — A data structure improving query performance by enabling fast lookups. Types: B-Tree (range queries), Hash (equality), GIN (full-text/arrays), GiST (geometric/spatial).

**Materialized View** — A precomputed query result stored as a table and periodically refreshed. Trades storage and freshness for dramatically faster read performance.

**MVCC** (Multi-Version Concurrency Control) — A concurrency control method where each transaction sees a snapshot of the database, avoiding read locks. Used by PostgreSQL, MySQL InnoDB, and Oracle.

**N+1 Problem** — A performance anti-pattern where fetching N related records requires N+1 queries (1 for the parent, N for each child). Solved by eager loading, JOINs, or DataLoader batching.

**NewSQL** — Databases providing SQL semantics and ACID guarantees with horizontal scalability. Examples: CockroachDB, TiDB, Google Spanner. The best of both SQL and NoSQL worlds.

**NoSQL** (Not Only SQL) — A category of databases not using traditional relational models. Includes document (MongoDB), key-value (Redis), column-family (Cassandra), and graph (Neo4j) stores.

**OLAP** (Online Analytical Processing) — Databases optimized for complex analytical queries over large datasets. Column-oriented stores like ClickHouse, BigQuery, and Redshift.

**OLTP** (Online Transaction Processing) — Databases optimized for fast, concurrent transactional operations. Row-oriented stores like PostgreSQL, MySQL, and DynamoDB.

**ORM** — See Architecture & Design. The bridge between relational data and object-oriented code.

**Partitioning** — Dividing a table into smaller pieces based on a key (range, list, or hash). Improves query performance and maintenance for large tables. Different from sharding (which splits across servers).

**Read Replica** — A read-only copy of a database receiving asynchronous replication from the primary. Offloads read traffic; introduces replication lag.

**Replication** — See Distributed Systems. Applied to databases for availability and read scaling.

**Sharding** — See Distributed Systems. The database-specific term for horizontal partitioning across servers.

**Snowflake Schema** — A normalized variation of the star schema where dimension tables are further broken into sub-dimensions. More storage-efficient but requires more JOINs.

**SQL** (Structured Query Language) — The standard language for relational database management. Despite decades of "SQL is dead" predictions, it remains the lingua franca of data.

**Star Schema** — A data warehouse modeling pattern with a central fact table surrounded by dimension tables. Optimized for analytical queries and BI tools.

**Vacuum** — A PostgreSQL maintenance process reclaiming storage from dead tuples left by MVCC. Autovacuum runs automatically, but understanding it prevents table bloat.

**WAL** — See Distributed Systems. In databases, the write-ahead log ensures crash recovery and replication.

**Window Function** — A SQL function performing calculations across a set of rows related to the current row without grouping. ROW_NUMBER, RANK, LAG, LEAD, SUM OVER are essential tools.

---

## Performance

**Amdahl's Law** — The theoretical speedup of a program is limited by the fraction that cannot be parallelized. If 10% is serial, maximum speedup is 10x regardless of core count.

**AOT** (Ahead-of-Time Compilation) — Compiling code to machine code before execution rather than at runtime. GraalVM Native Image and Go use AOT; reduces startup time but limits runtime optimizations.

**APM** (Application Performance Monitoring) — Tools providing visibility into application performance via traces, metrics, and logs. Datadog, New Relic, and Dynatrace are popular APM solutions.

**Bandwidth** — The maximum rate of data transfer across a network path. Often confused with throughput; bandwidth is capacity, throughput is actual usage.

**Cache Hit/Miss Ratio** — The proportion of requests served from cache vs. the origin. A 95% hit ratio means 95 of 100 requests don't hit the backend. Monitor this obsessively.

**Cache Stampede** — When a popular cache key expires and many requests simultaneously hit the backend to regenerate it. Mitigated by lock-based regeneration, probabilistic early expiration, or stale-while-revalidate.

**Cold Start** — The initial latency when a function or service handles its first request after being idle. Significant in serverless (Lambda), JVM applications, and newly scaled containers.

**False Sharing** — A performance issue where threads on different cores invalidate each other's cache lines by writing to adjacent memory locations. A subtle cause of poor multithreaded performance.

**Flame Graph** — A visualization of profiled code showing the call stack and time spent in each function. Created by Brendan Gregg; the single best tool for understanding where CPU time goes.

**G1GC** (Garbage-First Garbage Collector) — A JVM garbage collector dividing the heap into regions and prioritizing collection of regions with the most garbage. Default since Java 9.

**GC** (Garbage Collection) — Automatic memory management reclaiming unused objects. Understanding GC pauses is crucial for latency-sensitive applications in Java, Go, and C#.

**JIT** (Just-in-Time Compilation) — Compiling code to machine code at runtime based on observed execution patterns. JVMs and V8 use JIT to optimize hot paths.

**Latency** — The time between sending a request and receiving a response. Measured in milliseconds; p50 is median, p99 is the tail. Users feel latency; optimize it relentlessly.

**Little's Law** — L = lambda * W. The average number of items in a system equals the arrival rate times the average time each item spends. Fundamental for capacity planning.

**Lock Contention** — Performance degradation caused by threads waiting to acquire locks held by other threads. Resolved by reducing critical section size, using read-write locks, or lock-free algorithms.

**p50, p95, p99, p999** — Latency percentiles. p50 is the median, p99 means 99% of requests are faster than this value. p99 and p999 are where user pain lives; don't just monitor averages.

**Profiler** — A tool measuring where a program spends time (CPU profiler) or memory (heap profiler). Essential for optimization; never guess where bottlenecks are.

**QPS** (Queries Per Second) — A throughput metric for the number of queries a system handles per second. Used for databases and search systems.

**RPS** (Requests Per Second) — A throughput metric for the number of HTTP or API requests a system handles per second. The primary load metric for web services.

**Throughput** — The amount of work completed per unit of time. Can be measured in requests/second, messages/second, or bytes/second depending on context.

**Thundering Herd** — A burst of requests hitting a backend simultaneously, often after a cache miss, retry storm, or service recovery. Mitigated by jitter, backoff, and request coalescing.

**TPS** (Transactions Per Second) — A throughput metric for database or payment system performance. Critical for capacity planning in financial systems.

**TTL** (Time to Live) — The duration a cached value or DNS record is valid before expiring. Too short wastes resources; too long serves stale data.

**Warm Start** — Subsequent invocations of a function or service that reuse an already-initialized execution environment. Much faster than cold starts.

**ZGC** (Z Garbage Collector) — A JVM garbage collector designed for low-latency applications with sub-millisecond pause times. Suitable for heaps from megabytes to terabytes.

---

## Concurrency

**ABA Problem** — A concurrency issue where a value changes from A to B and back to A, making a compare-and-swap believe nothing changed. Solved with version counters or tagged pointers.

**Actor Model** — A concurrency model where actors are independent units communicating via messages with no shared state. Erlang/OTP, Akka, and Orleans implement this pattern.

**Atomic** — An operation that completes entirely or not at all, with no observable intermediate state. Atomic variables (AtomicInteger, atomic.Value) enable lock-free programming.

**Backpressure** — See Reliability & Operations. In concurrency, it's a flow control mechanism in reactive/streaming systems preventing producers from overwhelming consumers.

**CAS** (Compare-and-Swap) — An atomic CPU instruction comparing a memory location to an expected value and swapping it if they match. The building block of lock-free data structures.

**Channel** — A typed conduit for passing data between concurrent processes. Go channels and Rust channels implement CSP-style communication.

**Coroutine** — A generalization of subroutines allowing suspension and resumption. Kotlin coroutines, Python asyncio, and C# async/await use coroutines for cooperative concurrency.

**CSP** (Communicating Sequential Processes) — A concurrency model where processes communicate through channels. Go's goroutines and channels implement CSP principles.

**Deadlock** — A state where two or more threads are blocked forever, each waiting for the other to release a resource. Prevented by consistent lock ordering and timeouts.

**Event Loop** — A programming construct waiting for and dispatching events. Node.js, browser JavaScript, and asyncio use event loops for single-threaded concurrency.

**Goroutine** — Go's lightweight concurrent function, multiplexed onto OS threads by the runtime. Cheaper than threads (starting at ~2KB stack); millions can run concurrently.

**Green Thread** — A thread managed by a runtime or VM rather than the OS. Lighter than OS threads; Java's virtual threads (Project Loom) and Erlang processes are examples.

**Happens-Before** — A relation defining the ordering of operations in concurrent programs. If A happens-before B, the effects of A are visible to B. Foundational to memory models.

**Livelock** — A state where threads are not blocked but make no progress because they keep responding to each other. Like two people stepping aside for each other in a corridor.

**Lock-Free** — An algorithm guaranteeing system-wide progress; at least one thread makes progress even if others are delayed. Uses CAS operations instead of locks.

**Memory Barrier** (Memory Fence) — A CPU instruction ensuring memory operations before the barrier are visible before operations after it. Necessary for correct lock-free programming.

**Mutex** (Mutual Exclusion) — A synchronization primitive allowing only one thread to access a resource at a time. The simplest locking mechanism; use when you need exclusive access.

**Process** — An independent execution environment with its own memory space. Heavier than threads; provides strong isolation. Used for multi-core parallelism and fault isolation.

**Race Condition** — A bug where behavior depends on the timing of uncontrolled events (thread scheduling). Detected by tools like ThreadSanitizer; prevented by proper synchronization.

**Reactive Streams** — A specification for asynchronous stream processing with non-blocking backpressure. Implemented by RxJava, Project Reactor, and Akka Streams.

**RWLock** (Read-Write Lock) — A lock allowing multiple concurrent readers but exclusive writers. Improves performance when reads far outnumber writes.

**Semaphore** — A synchronization primitive controlling access to a resource with a counter. Unlike a mutex, allows multiple threads up to a defined limit (e.g., connection pool size).

**Sequential Consistency** — A memory model where operations appear to execute in some total order consistent with each thread's program order. Stronger than what most hardware provides by default.

**Starvation** — A condition where a thread cannot get the resources it needs because other threads are monopolizing them. Can occur with unfair locks or priority inversion.

**Thread** — The smallest unit of execution scheduled by the OS. Shares memory with other threads in the same process; cheaper than processes but requires synchronization.

**Wait-Free** — A stronger guarantee than lock-free: every thread makes progress in a bounded number of steps. Extremely difficult to implement; used in real-time systems.

---

## Testing

**Arrange-Act-Assert** (AAA) — A test structure pattern: set up the conditions (Arrange), execute the behavior (Act), verify the result (Assert). The standard structure for unit tests.

**ATDD** (Acceptance Test-Driven Development) — Writing acceptance tests before implementation to define done from the user's perspective. Tests are often written in collaboration with stakeholders.

**BDD** (Behavior-Driven Development) — A development approach writing tests in natural language (Given-When-Then) to describe behavior. Tools: Cucumber, SpecFlow, Behave.

**Branch Coverage** — A metric measuring the percentage of code branches (if/else, switch) executed by tests. More thorough than line coverage; a branch coverage of 80%+ is a reasonable target.

**Code Coverage** — The percentage of code lines executed during testing. Useful as a trend indicator but not a quality guarantee; 100% coverage can still miss bugs.

**Contract Test** — A test verifying that a service adheres to the API contract expected by its consumers. Pact is the most popular contract testing tool; catches integration issues without E2E tests.

**E2E** (End-to-End Test) — A test validating the entire system flow from user input to final output. Slowest but highest-confidence; use sparingly for critical paths. Tools: Playwright, Cypress.

**Factory** — A testing utility creating test objects with default values that can be overridden. More flexible than fixtures; libraries like FactoryBot, Fishery, and factory_boy.

**Fake** — A working implementation of a dependency with simplified behavior (e.g., an in-memory database). More realistic than mocks but simpler than the real thing.

**Fixture** — Predefined test data or environment state set up before tests run. Can be static data files or programmatic setup. Keep fixtures minimal and meaningful.

**Flaky Test** — A test that passes and fails intermittently without code changes. Caused by timing issues, shared state, or external dependencies. Flaky tests erode trust in the test suite.

**Given-When-Then** — A BDD test structure: Given a precondition, When an action occurs, Then an expected result follows. Maps naturally to business requirements.

**Integration Test** — A test verifying that multiple components work together correctly. Broader than unit tests, narrower than E2E; tests real database queries, API calls, etc.

**Mock** — A test double recording interactions and verifying expected calls. Differs from stubs (which return canned responses) and fakes (which have working implementations).

**Mutation Test** — A technique modifying (mutating) source code and checking if tests catch the change. Measures test suite effectiveness; tools: Stryker, PIT, mutmut.

**Mutation Score** — The percentage of code mutations killed (detected) by the test suite. Higher scores indicate more effective tests; aim for 80%+.

**Property-Based Test** — A test checking that a property holds for all generated inputs rather than specific examples. Tools: Hypothesis (Python), fast-check (JS), QuickCheck (Haskell).

**Regression Test** — A test ensuring previously fixed bugs or working features are not broken by new changes. Often automated and run in CI on every commit.

**Smoke Test** — A quick, high-level test verifying basic functionality works after a deployment. "Does the application start? Can users log in?" Not exhaustive.

**Snapshot Test** — A test capturing the output of a component (rendered UI, API response) and comparing future runs against the saved snapshot. Easy to create; can lead to brittle tests.

**Spy** — A test double that wraps a real implementation and records calls made to it. Useful when you want real behavior but also need to verify interactions.

**Stub** — A test double providing canned responses to method calls. Simpler than mocks; useful when you care about the return value, not how it was called.

**TDD** (Test-Driven Development) — Writing tests before writing the code that makes them pass. Red-Green-Refactor: write a failing test, make it pass, then refactor.

**Test Double** — A generic term for any object used in place of a real dependency in tests. Encompasses mocks, stubs, spies, fakes, and dummies.

**Unit Test** — A test verifying a single function or class in isolation. Fast, focused, and numerous; the base of the test pyramid.

---

## AI/ML Engineering

**Agent** — An AI system that can autonomously plan, use tools, and take actions to accomplish goals. Goes beyond simple prompting by iterating on tasks with external system access.

**Chain-of-Thought** (CoT) — A prompting technique encouraging LLMs to show reasoning steps before answering. Significantly improves performance on math, logic, and multi-step problems.

**Context Window** — The maximum number of tokens an LLM can process in a single prompt plus response. GPT-4 Turbo: 128K, Claude: 200K. Limits how much context you can provide.

**Cosine Similarity** — A metric measuring the angle between two vectors, commonly used to compare embeddings. Values range from -1 to 1; higher means more similar.

**Embedding** — A dense vector representation of text, images, or other data in a continuous vector space. Enables semantic search, clustering, and similarity comparison.

**Eval** (Evaluation) — Systematic testing of AI model or system outputs against defined criteria. The "unit tests" of AI engineering; essential for measuring prompt and model changes.

**Few-shot** — Providing a few examples in the prompt to guide the model's behavior. More effective than zero-shot for complex or domain-specific tasks.

**Fine-tuning** — Training a pre-trained model on task-specific data to improve performance. More targeted than prompting but requires data, compute, and ongoing maintenance.

**Function Calling** (Tool Use) — An LLM capability to output structured requests to call external functions or APIs. Enables AI agents to interact with databases, APIs, and real-world systems.

**Grounding** — Connecting LLM outputs to factual, verifiable sources of information. RAG is one grounding technique; reduces hallucinations by anchoring responses in real data.

**Guardrails** — Safety mechanisms constraining AI system behavior to prevent harmful, off-topic, or incorrect outputs. Implemented as input/output filters, classifiers, or constitutional AI techniques.

**Hallucination** — When an LLM generates plausible but factually incorrect information with confidence. The fundamental reliability challenge of generative AI.

**LLM** (Large Language Model) — A neural network trained on vast text corpora to understand and generate language. GPT-4, Claude, Gemini, and Llama are prominent examples.

**LoRA** (Low-Rank Adaptation) — A parameter-efficient fine-tuning technique that trains small adapter matrices instead of the full model. Dramatically reduces compute and memory requirements.

**MCP** (Model Context Protocol) — An open protocol for connecting AI models to external tools, data sources, and services. Standardizes how AI agents interact with the world.

**Prompt Engineering** — The practice of designing and optimizing prompts to elicit desired LLM behavior. Includes techniques like few-shot, chain-of-thought, and system prompts.

**QLoRA** (Quantized LoRA) — Combining LoRA with model quantization for even more efficient fine-tuning. Enables fine-tuning large models on consumer GPUs.

**RAG** (Retrieval-Augmented Generation) — A pattern retrieving relevant documents from a knowledge base and including them in the LLM prompt. Reduces hallucination and keeps responses current.

**ReAct** (Reasoning + Acting) — An agent pattern where the LLM alternates between reasoning about what to do and taking actions. Combines chain-of-thought with tool use.

**RLHF** (Reinforcement Learning from Human Feedback) — A training technique where human preferences guide model optimization. Key to aligning LLMs with human values and expectations.

**Temperature** — A parameter controlling randomness in LLM outputs. Lower (0.0) is more deterministic and focused; higher (1.0+) is more creative and varied.

**Token** — The fundamental unit of text processed by an LLM. Roughly 3/4 of a word in English. Token counts determine costs, context limits, and processing time.

**Top-p** (Nucleus Sampling) — A sampling parameter limiting token selection to the smallest set whose cumulative probability exceeds p. An alternative to temperature for controlling output diversity.

**Vector Database** — A database optimized for storing and querying high-dimensional vectors (embeddings). Pinecone, Weaviate, Milvus, and pgvector enable semantic search at scale.

**Zero-shot** — Asking an LLM to perform a task without providing examples, relying entirely on its training. Works well for common tasks; less reliable for domain-specific ones.

---

## Cloud & AWS Specific

**ALB** (Application Load Balancer) — An AWS L7 load balancer routing HTTP/HTTPS traffic based on path, host, headers, and query parameters. Supports WebSockets and gRPC.

**Aurora** — AWS's MySQL/PostgreSQL-compatible relational database with up to 5x throughput improvement. Supports serverless auto-scaling and global databases.

**CDK** — See DevOps & Infrastructure. AWS's IaC framework using real programming languages.

**CloudFormation** — AWS's native IaC service using JSON/YAML templates to provision resources. The foundation that CDK compiles to.

**CloudFront** — AWS's CDN distributing content globally with edge caching. Integrates with S3, ALB, Lambda@Edge, and CloudFront Functions.

**CloudWatch** — AWS's monitoring and observability service for metrics, logs, alarms, and dashboards. The default monitoring tool for all AWS resources.

**DynamoDB** — AWS's fully managed NoSQL key-value and document database. Single-digit millisecond latency at any scale; designed for high-throughput applications.

**EC2** (Elastic Compute Cloud) — AWS's virtual server service. The building block of AWS; available in hundreds of instance types optimized for compute, memory, storage, and GPU.

**ECS** (Elastic Container Service) — AWS's container orchestration service. Simpler than EKS; runs containers on EC2 or Fargate without managing Kubernetes.

**EKS** (Elastic Kubernetes Service) — AWS's managed Kubernetes service. Run standard Kubernetes workloads with AWS managing the control plane.

**ElastiCache** — AWS's managed in-memory caching service supporting Redis and Memcached. Used for session stores, leaderboards, and database query caching.

**EventBridge** — AWS's serverless event bus connecting applications using events. Routes events from AWS services, SaaS apps, and custom sources to targets.

**Fargate** — AWS's serverless compute engine for containers (ECS and EKS). No server management; you define CPU and memory per task.

**IAM** (Identity and Access Management) — AWS's service for managing access to resources via users, roles, and policies. The most critical AWS service to understand well.

**Kinesis** — AWS's managed streaming data service for real-time data processing. Alternatives: Kafka (MSK), but Kinesis is simpler for AWS-native workloads.

**KMS** — See Security. AWS's managed encryption key service integrated with nearly every AWS resource.

**Lambda** — AWS's serverless compute service running code in response to events. Pay per invocation; scales to zero. The poster child of serverless architecture.

**NACL** (Network Access Control List) — A stateless firewall at the subnet level in a VPC. Coarser than security groups; evaluated before security group rules.

**NAT Gateway** — An AWS service enabling private subnet instances to access the internet without being publicly reachable. A significant cost item in VPC architectures.

**NLB** (Network Load Balancer) — An AWS L4 load balancer handling millions of requests per second with ultra-low latency. Operates at the TCP/UDP level.

**PrivateLink** — An AWS service providing private connectivity to services without traversing the public internet. Exposes services via VPC endpoints.

**RDS** (Relational Database Service) — AWS's managed relational database service supporting PostgreSQL, MySQL, MariaDB, Oracle, and SQL Server. Handles backups, patching, and replication.

**Route 53** — AWS's DNS and domain registration service. Named after the DNS port (53); supports routing policies like weighted, latency-based, and failover.

**S3** (Simple Storage Service) — AWS's object storage service with virtually unlimited capacity and 99.999999999% durability. The foundation for data lakes, backups, and static hosting.

**Secrets Manager** — AWS's service for storing, rotating, and managing secrets (database credentials, API keys). Integrates with RDS for automatic credential rotation.

**Security Group** — A stateful virtual firewall controlling inbound and outbound traffic to AWS resources. The primary network security mechanism for EC2, RDS, and Lambda.

**SNS** (Simple Notification Service) — AWS's fully managed pub/sub messaging service. Delivers messages to SQS queues, Lambda functions, HTTP endpoints, and email/SMS.

**SQS** (Simple Queue Service) — AWS's fully managed message queuing service. Standard queues (at-least-once, best-effort ordering) and FIFO queues (exactly-once, ordered).

**Step Functions** — AWS's serverless workflow orchestration service using state machines. Coordinates Lambda functions, ECS tasks, and other services with built-in error handling and retries.

**Systems Manager** (SSM) — AWS's operations management service for patching, configuration, secrets (Parameter Store), and remote access (Session Manager). The Swiss Army knife of AWS ops.

**Transit Gateway** — An AWS service connecting multiple VPCs and on-premises networks through a central hub. Simplifies complex networking topologies.

**VPC** — See Networking & Protocols. In AWS, the foundational network construct for isolating resources.

**X-Ray** — AWS's distributed tracing service for analyzing and debugging production applications. Visualizes request flows across microservices.

---

## Metrics & Processes

**ADR** (Architecture Decision Record) — A document capturing an important architectural decision along with its context and consequences. Track decisions in version control alongside code.

**Bikeshedding** — Spending disproportionate time on trivial issues while ignoring important ones. Named after Parkinson's observation that committees debate bike shed colors while rubber-stamping nuclear reactors.

**Boy Scout Rule** — "Always leave the code better than you found it." Make small improvements (rename a variable, extract a method) whenever you touch existing code.

**Brooks's Law** — "Adding people to a late software project makes it later." Communication overhead grows quadratically with team size; a core argument in The Mythical Man-Month.

**Burndown Chart** — A chart showing remaining work over time in a sprint. The slope indicates if the team is on track. Useful but only if estimates are calibrated.

**Change Failure Rate** — The percentage of deployments causing failures in production. One of the four DORA metrics; elite teams achieve < 15%.

**Code Smell** — A surface indication of a deeper problem in code. Examples: long methods, large classes, feature envy, god objects. Not bugs, but warning signs.

**Conway's Law** — "Organizations design systems that mirror their communication structure." If you have four teams, you'll get a four-component architecture. Deliberately structure teams around desired architecture.

**Cycle Time** — The time from work starting to work completing. Includes development, review, testing, and deployment. A more actionable metric than lead time for individual items.

**Deployment Frequency** — How often code is deployed to production. One of the four DORA metrics; elite teams deploy on demand (multiple times per day).

**DORA Metrics** — Four key metrics measuring software delivery performance: Deployment Frequency, Lead Time for Changes, Change Failure Rate, and MTTR. From the Accelerate book by Nicole Forsgren et al.

**DRY** (Don't Repeat Yourself) — A principle stating that every piece of knowledge should have a single, authoritative representation. Overapplied DRY causes premature abstraction; balance with readability.

**Flow Efficiency** — The ratio of active work time to total cycle time. If an item takes 10 days but only 2 are active work, flow efficiency is 20%. Reveals queueing waste.

**Goodhart's Law** — "When a measure becomes a target, it ceases to be a good measure." If you reward lines of code, people write verbose code. Design metrics carefully.

**Hyrum's Law** — "With a sufficient number of users, every observable behavior of your system will be depended on by someone." You can't change anything without breaking someone.

**Kanban** — A visual workflow management method using cards on a board with WIP (work-in-progress) limits. Focuses on continuous flow rather than fixed iterations.

**KISS** (Keep It Simple, Stupid) — A design principle favoring simplicity over complexity. The simplest solution that works is usually the best one.

**Lead Time** — The time from code commit to production deployment. One of the four DORA metrics; elite teams achieve less than one day.

**MTTR** — See Reliability & Operations. Also one of the four DORA metrics measuring recovery speed.

**Refactoring** — Restructuring existing code without changing its external behavior. Improves readability, reduces complexity, and makes future changes easier.

**Retrospective** — A team ceremony reflecting on what went well, what didn't, and what to improve. Held at the end of sprints or after incidents. Only valuable if it leads to action items.

**RFC** (Request for Comments) — A document proposing a significant technical change for team review and discussion. Ensures alignment before investing in implementation.

**Scrum** — An agile framework with fixed-length sprints, defined roles (Scrum Master, Product Owner), and ceremonies (standup, planning, review, retro). The most widely adopted agile methodology.

**SOLID** — Five object-oriented design principles: Single Responsibility, Open-Closed, Liskov Substitution, Interface Segregation, Dependency Inversion. Guidelines, not laws; apply with judgment.

**SPACE Framework** — A framework for measuring developer productivity across five dimensions: Satisfaction, Performance, Activity, Communication, Efficiency. More nuanced than single metrics.

**Sprint** — A fixed-duration iteration (usually 1-4 weeks) in Scrum during which a team delivers a potentially shippable increment. The heartbeat of Scrum.

**Standup** (Daily Scrum) — A brief daily meeting where team members share progress, plans, and blockers. Should be 15 minutes or less; not a status report to management.

**Story Points** — An abstract unit estimating the effort/complexity of a work item. Controversial and often misused; useful for relative sizing within a team, meaningless across teams.

**Tech Debt** (Technical Debt) — The accumulated cost of shortcuts, outdated patterns, and deferred maintenance in a codebase. Intentional debt is a strategy; unintentional debt is a problem.

**Velocity** — The average story points completed per sprint. A planning tool, not a performance metric. Comparing velocity across teams is meaningless and harmful.

**YAGNI** (You Ain't Gonna Need It) — A principle against implementing features based on speculation about future needs. Build what you need now; extend when the need is real.

---

## Slang & Culture

**10x Engineer** — A (contentious) notion that some engineers are ten times more productive than average. Often misunderstood as raw output; real 10x engineers multiply the team's effectiveness.

**ACK** — Acknowledgment. Used in code reviews and messaging to confirm you've seen something and agree. Opposite of NACK.

**Big Bang** — A migration or launch approach that switches everything at once rather than incrementally. High risk, high drama. Usually contrasted with the Strangler Fig pattern.

**Blameless** — A cultural principle that postmortems and incident reviews focus on systemic causes rather than individual blame. Essential for building trust and improving reliability.

**Brownfield** — An existing project with legacy code, established patterns, and accumulated tech debt. The opposite of greenfield; where most real engineering happens.

**Bus Factor** — The number of team members whose departure would critically impact the project. A bus factor of 1 means a single person leaving could stall everything. Increase it through documentation and knowledge sharing.

**Conway's Law** — See Metrics & Processes. "You ship your org chart."

**DevOps** — A culture and practice unifying development and operations to improve deployment frequency, reliability, and collaboration. Not a job title; a way of working.

**Dogfooding** — Using your own product internally before releasing it. "Eating your own dog food." Surfaces usability issues and builds empathy with users.

**Fail Fast** — A design principle where systems detect and report errors immediately rather than silently continuing. Applied to input validation, health checks, and startup checks.

**Fail Forward** — Treating failures as learning opportunities and moving forward with improvements rather than rolling back to the status quo. A growth mindset applied to engineering.

**Footgun** — A feature or API that makes it easy to "shoot yourself in the foot." A tool that's dangerous if misused. "That method signature is a real footgun."

**Footprint** — The resource consumption (memory, disk, CPU) of a system or component. "What's the memory footprint of this service?"

**Golden Path** (Paved Road) — The recommended, well-supported way to build and deploy services in an organization. Platform engineering's primary product; reduces cognitive load by providing sane defaults.

**Greenfield** — A new project with no existing code or constraints. The opposite of brownfield; exciting but rare. Resist the urge to over-engineer.

**LGTM** (Looks Good to Me) — A code review approval indicating the reviewer is satisfied with the changes. The two most satisfying words in a pull request.

**NACK** (Negative Acknowledgment) — Rejection or disagreement in code reviews and discussions. "I'm going to NACK this approach because of the performance implications."

**Ops** — Short for operations; the work of keeping systems running in production. Includes monitoring, incident response, capacity planning, and deployments.

**Paved Road** — See Golden Path. The organization's supported and maintained path for common engineering tasks.

**Pets vs Cattle** — A metaphor for server management philosophy. Pets are unique, manually maintained servers you nurse back to health. Cattle are identical, disposable instances you replace when they fail.

**Platform Engineering** — The discipline of building and maintaining internal developer platforms that enable self-service infrastructure and tooling. The evolution of DevOps.

**PTAL** (Please Take A Look) — A request for someone to review your code, document, or proposal. Common in code review comments and Slack messages.

**RTFM** (Read The Fine Manual) — A blunt suggestion to consult the documentation before asking questions. Use diplomatically; better yet, make the docs so good people want to read them.

**Rubber Ducking** — Explaining a problem to an inanimate object (like a rubber duck) to discover the solution yourself. The act of articulating the problem often reveals the answer.

**Shift Left** — Moving activities (testing, security, performance) earlier in the development lifecycle. "Shift left on security" means finding vulnerabilities during development, not in production.

**Ship It** — An emphatic declaration that something is ready for production. Can be genuine ("Ship it!") or ironic ("It compiled? Ship it.").

**SRE** — See Reliability & Operations. Also increasingly used as a cultural identifier for reliability-focused engineering practices.

**Strangler Fig** — See Architecture & Design. Used colloquially for any gradual replacement strategy.

**Tech Debt** — See Metrics & Processes. Used in everyday conversation: "We need to pay down some tech debt before the next feature."

**TIL** (Today I Learned) — A common prefix for sharing a new discovery with the team. "TIL you can use `git bisect` to find the commit that introduced a bug."

**Toil** — See Reliability & Operations. In slang: any boring, repetitive work that should be automated.

**WIP** (Work In Progress) — A draft or incomplete piece of work. "WIP" in a PR title signals it's not ready for review. Limiting WIP is a core Kanban principle.

**Yak Shaving** — The seemingly endless series of small tasks you have to complete before you can tackle the actual task. "I needed to deploy, so I had to fix the pipeline, which required updating the plugin, which needed a new Node version..."

---

*This glossary contains 250+ entries spanning 14 categories. Terms appearing in multiple contexts are cross-referenced. When in doubt, ctrl+F is your friend.*

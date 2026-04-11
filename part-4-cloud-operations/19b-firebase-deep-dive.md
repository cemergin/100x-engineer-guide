<!--
  CHAPTER: 19b
  TITLE: Firebase Deep Dive
  PART: IV — Cloud & Operations
  PREREQS: Chapter 7 (infrastructure concepts), Chapter 13 (system integration), Chapter 19 (AWS Deep Dive)
  KEY_TOPICS: Firestore, Firebase Auth, Cloud Functions, security rules, Realtime Database, Firebase Hosting, Firebase + Next.js, scaling Firebase
  DIFFICULTY: Intermediate → Advanced
  UPDATED: 2026-03-24
-->

# Chapter 19b: Firebase Deep Dive

> **Part IV — Cloud & Operations** | Prerequisites: Chapter 7 (infrastructure concepts), Chapter 13 (system integration) | Difficulty: Intermediate → Advanced

Firebase is Google's Backend-as-a-Service (BaaS) platform, and it occupies a unique niche in the cloud landscape. Where AWS (Chapter 19) gives you 200+ building blocks and expects you to wire them together, Firebase gives you a pre-wired backend that a three-person team can ship a real-time app on in a weekend. Authentication, a real-time database, file storage, serverless functions, and hosting — all managed, all integrated, all working together from a single Firebase project.

The tradeoff is real: Firebase is not a replacement for AWS or GCP for complex backends. It's optimized for a specific class of apps — rapid prototypes, real-time applications, mobile-first products, small to medium teams. When you're in that class, Firebase is brilliant. When you're not, you'll feel the constraints. This chapter covers both sides honestly.

Firebase is built on Google Cloud Platform under the hood. Cloud Functions are Cloud Run. Firestore is a GCP product. You can mix Firebase services with full GCP services when needed — you're not trapped. See Chapter 31 (GCP deep dive) for the full GCP picture, where Firestore appears again without the Firebase wrapper.

### In This Chapter
- Firebase Services Map
- Core Services (Firestore, Realtime Database, Auth, Cloud Functions, Hosting, Storage)
- Firebase Security Rules
- Firebase + Modern Frameworks
- Scaling Firebase
- Firebase vs AWS Comparison
- Firebase CLI Cheat Sheet

### Related Chapters
- [Chapter 19: AWS Deep Dive](./19-aws-deep-dive.md)
- Chapter 13 (how cloud services connect)
- Chapter 7 (infrastructure/K8s)
- Chapter 5 (security/IAM)
- Chapter 31 (GCP deep dive)

---

## 1. FIREBASE SERVICES MAP

### 1.1 What Firebase Is (and Is Not)

Firebase is Google's Backend-as-a-Service (BaaS) platform. The value proposition is simple: skip the server. Firebase gives you authentication, a real-time database, file storage, serverless functions, and hosting — all managed, all integrated, all working together from a single Firebase project. A two-person team can build a full-stack real-time app in a week.

But Firebase is not a replacement for AWS or GCP for complex backends. It's optimized for a specific class of apps — and when you're in that class, it's brilliant. When you're not, you'll feel the constraints.

**Firebase is NOT:**
- A replacement for AWS or GCP for complex backends
- Suitable for all workloads (compute-heavy, complex querying, multi-tenancy at scale)
- Free at scale (costs grow with reads/writes, can surprise you)

**Where Firebase fits:** Rapid prototyping, real-time apps, mobile-first products, small to medium teams. Firebase excels when your data model fits its document-oriented design and you want to ship fast.

**Firebase is built on Google Cloud Platform.** Cloud Functions are Cloud Run under the hood. Firestore is a GCP product. You can mix Firebase services with full GCP services when needed. This is worth remembering when you need to extend beyond what Firebase's abstraction layer offers — you're not trapped.

Compare this to Chapter 31 (GCP deep dive), where Firestore appears again without the Firebase wrapper. Same underlying service, different interface and mental model.

### 1.2 Firebase Project Structure

```
Firebase Project (= GCP Project)
├── Apps
│   ├── iOS App (bundle ID)
│   ├── Android App (package name)
│   └── Web App (config object)
├── Firestore Database
├── Realtime Database (can have multiple)
├── Authentication
├── Cloud Functions
├── Hosting
├── Storage (= GCS bucket)
└── Extensions (pre-built solutions)
```

**Multi-environment setup:** Create separate Firebase projects for dev/staging/production. Use `.firebaserc` to manage aliases:

```json
{
  "projects": {
    "default": "my-app-dev",
    "staging": "my-app-staging",
    "production": "my-app-prod"
  }
}
```

```bash
# Initialize Firebase in your project
firebase init

# Switch between environments
firebase use staging
firebase use production

# Deploy to a specific environment
firebase deploy --project my-app-prod
```

---

## 2. CORE SERVICES

### 2.1 Firestore

Firestore is a serverless NoSQL document database that does two things most databases don't: real-time synchronization and offline support. When a document changes in Firestore, every client listening to that document gets the update automatically — no polling, no websocket management, no server-side push logic. You write the data once; Firestore handles the delivery.

The offline support is genuinely impressive. Reads return cached data when offline. Writes are queued locally and synced when connectivity returns. For mobile apps, this makes Firestore feel magic.

**Data model:**
```
Collection: users/
  Document: user123
    Fields: { name: "Alice", email: "alice@example.com", createdAt: Timestamp }
    Subcollection: orders/
      Document: order456
        Fields: { total: 99.99, status: "shipped", items: [...] }
```

**Key rules:**
- Documents are limited to 1 MB
- Collections contain only documents (no nested collections without going through a document)
- Document IDs must be unique within a collection
- Maximum document nesting: 100 levels (via subcollections)

**Queries:**

```javascript
import { collection, query, where, orderBy, limit, getDocs, onSnapshot } from 'firebase/firestore';

// Simple query
const q = query(
  collection(db, 'orders'),
  where('status', '==', 'pending'),
  where('total', '>', 100),
  orderBy('total', 'desc'),
  limit(25)
);
const snapshot = await getDocs(q);

// Array-contains (find documents where tags array includes 'urgent')
const q2 = query(
  collection(db, 'orders'),
  where('tags', 'array-contains', 'urgent')
);

// 'in' query (up to 30 values)
const q3 = query(
  collection(db, 'users'),
  where('status', 'in', ['active', 'trial'])
);

// Real-time listener
const unsubscribe = onSnapshot(q, (snapshot) => {
  snapshot.docChanges().forEach((change) => {
    if (change.type === 'added') console.log('New:', change.doc.data());
    if (change.type === 'modified') console.log('Modified:', change.doc.data());
    if (change.type === 'removed') console.log('Removed:', change.doc.data());
  });
});

// Collection group query (query across all subcollections with the same name)
const allOrders = query(
  collectionGroup(db, 'orders'),
  where('status', '==', 'pending')
);
```

**Indexes:**
- **Single-field indexes:** Automatically created for every field. Supports `==`, `<`, `>`, `array-contains`.
- **Composite indexes:** Required for queries combining multiple fields with inequality or ordering. Must be created explicitly (Firestore error messages include the exact index creation link).

```bash
# Deploy indexes defined in firestore.indexes.json
firebase deploy --only firestore:indexes
```

**Offline persistence:** Enabled by default on mobile (iOS/Android). For web:
```javascript
import { enableIndexedDbPersistence } from 'firebase/firestore';
enableIndexedDbPersistence(db);
```

Reads return cached data when offline. Writes are queued and synced when connectivity returns.

**Pricing model:**
- Document reads: $0.06 per 100K
- Document writes: $0.18 per 100K
- Document deletes: $0.02 per 100K
- Storage: $0.18 per GB/month
- Free tier: 50K reads, 20K writes, 20K deletes per day

**Common gotchas:**
- Reads are billed per document returned. A query returning 1000 documents costs 1000 reads, even if you only need one field. Design queries to return minimal documents.
- `in` and `array-contains-any` operators are limited to 30 values (as of 2024, increased from 10).
- Firestore does not support full-text search. Use Algolia, Typesense, or a Cloud Function with Elasticsearch.
- Inequality filters (`<`, `>`, `!=`) can only be applied to a single field per query (relaxed in 2023 -- multiple inequality filters now supported but require composite indexes).

### 2.2 Realtime Database

**What it is:** Firebase's original database. A giant JSON tree with real-time synchronization.

Realtime Database predates Firestore and has a simpler model: it's a JSON tree, everything is a string or a number or an object or an array, and changes propagate to all listeners in real time. Firestore is better for most use cases now, but Realtime Database has some specific advantages worth knowing.

**When to use instead of Firestore:**
- Very low latency requirements (Realtime DB has ~10ms latency vs Firestore's ~30ms)
- Simple key-value presence systems (online/offline status)
- You need client-side fan-out writes (write to multiple locations atomically in one update)
- Cost optimization for high-frequency small reads (Realtime DB charges by bandwidth, not per-read)

**Data modeling -- keep it flat:**
```json
{
  "users": {
    "user123": { "name": "Alice", "email": "alice@example.com" }
  },
  "userOrders": {
    "user123": {
      "order456": true,
      "order789": true
    }
  },
  "orders": {
    "order456": { "total": 99.99, "status": "shipped" },
    "order789": { "total": 49.99, "status": "pending" }
  }
}
```

**Why flat?** When you read a node, you download ALL data under it (including nested children). Deep nesting means downloading unnecessary data. This is the most common Realtime Database mistake.

**Pricing:** Based on data stored ($5/GB/month) and data downloaded ($1/GB). No per-operation charge. This makes it cheaper than Firestore for high-frequency small reads.

### 2.3 Authentication

**What it is:** Complete authentication system supporting multiple providers, with client SDKs and server-side verification.

Firebase Auth handles the hardest parts of auth: the OAuth flows, the token management, the account linking, the password reset emails. You configure providers in the console; it handles the rest.

**Supported providers:**
- Email/Password (with email verification, password reset)
- Google, Apple, Facebook, Twitter, GitHub, Microsoft
- Phone (SMS verification)
- Anonymous (convert to permanent later)
- Custom tokens (integrate with any auth system)
- SAML and OIDC (enterprise SSO)

**Client-side usage:**

```javascript
import {
  getAuth, signInWithEmailAndPassword, signInWithPopup,
  GoogleAuthProvider, onAuthStateChanged, signOut
} from 'firebase/auth';

const auth = getAuth();

// Email/password sign-in
await signInWithEmailAndPassword(auth, 'user@example.com', 'password123');

// Google sign-in
const provider = new GoogleAuthProvider();
provider.addScope('profile');
const result = await signInWithPopup(auth, provider);
const credential = GoogleAuthProvider.credentialFromResult(result);

// Listen for auth state changes (fires on page load if user is logged in)
onAuthStateChanged(auth, (user) => {
  if (user) {
    console.log('Signed in:', user.uid, user.email);
    const token = await user.getIdToken(); // JWT for server verification
  } else {
    console.log('Signed out');
  }
});

// Anonymous auth (useful for shopping carts before sign-up)
import { signInAnonymously, linkWithCredential, EmailAuthProvider } from 'firebase/auth';
await signInAnonymously(auth);
// Later, upgrade to permanent account:
const credential = EmailAuthProvider.credential('user@example.com', 'password');
await linkWithCredential(auth.currentUser, credential);
```

**Server-side verification (Admin SDK):**

```javascript
const admin = require('firebase-admin');
admin.initializeApp();

// Verify ID token from client
async function verifyRequest(req, res, next) {
  const token = req.headers.authorization?.split('Bearer ')[1];
  if (!token) return res.status(401).json({ error: 'No token provided' });

  try {
    const decoded = await admin.auth().verifyIdToken(token);
    req.user = decoded; // { uid, email, ... }
    next();
  } catch (error) {
    res.status(401).json({ error: 'Invalid token' });
  }
}

// Create custom token (for integrating with external auth)
const customToken = await admin.auth().createCustomToken(uid, { role: 'admin' });

// Set custom claims (for role-based access)
await admin.auth().setCustomUserClaims(uid, { admin: true, orgId: 'acme' });
```

**Pricing:** Free for most auth methods. Phone auth: $0.01-0.06/verification (volume-based). SAML/OIDC: requires Identity Platform upgrade (50 free MAU, then $0.0055/MAU).

### 2.4 Cloud Functions

**What it is:** Serverless functions triggered by Firebase/GCP events or HTTP requests. V2 functions run on Cloud Run (better scaling, longer timeouts, concurrency).

Cloud Functions are how you add server-side logic to Firebase without managing a server. Firestore trigger fires when a document is created, you send an email. Storage trigger fires when a file is uploaded, you resize it. Auth trigger fires when a user signs up, you validate their email domain. All the things you'd otherwise need a server for, handled in individual functions.

**Trigger types:**

```javascript
const { onRequest } = require('firebase-functions/v2/https');
const { onDocumentCreated, onDocumentUpdated } = require('firebase-functions/v2/firestore');
const { onObjectFinalized } = require('firebase-functions/v2/storage');
const { beforeUserCreated } = require('firebase-functions/v2/identity');
const { onSchedule } = require('firebase-functions/v2/scheduler');
const { onMessagePublished } = require('firebase-functions/v2/pubsub');

// HTTP trigger
exports.api = onRequest({ cors: true, memory: '256MiB', region: 'us-central1' }, async (req, res) => {
  res.json({ message: 'Hello from Firebase!' });
});

// Firestore trigger -- runs when a new order is created
exports.onNewOrder = onDocumentCreated('orders/{orderId}', async (event) => {
  const order = event.data.data();
  const orderId = event.params.orderId;
  // Send confirmation email, update analytics, etc.
  await sendOrderConfirmation(order.email, orderId);
});

// Firestore trigger -- runs when order status changes
exports.onOrderUpdate = onDocumentUpdated('orders/{orderId}', async (event) => {
  const before = event.data.before.data();
  const after = event.data.after.data();
  if (before.status !== after.status && after.status === 'shipped') {
    await sendShippingNotification(after.email);
  }
});

// Storage trigger -- resize uploaded images
exports.onImageUpload = onObjectFinalized({ bucket: 'my-app.appspot.com' }, async (event) => {
  const filePath = event.data.name;
  if (!filePath.startsWith('uploads/') || filePath.includes('_thumb')) return;
  await generateThumbnail(filePath);
});

// Scheduled function (cron)
exports.dailyCleanup = onSchedule('every day 02:00', async (event) => {
  await deleteExpiredSessions();
});

// Auth trigger -- block sign-ups from non-company emails
exports.beforeCreate = beforeUserCreated((event) => {
  const email = event.data.email;
  if (!email?.endsWith('@mycompany.com')) {
    throw new HttpsError('permission-denied', 'Unauthorized email domain');
  }
});
```

**V1 vs V2 functions:**

| Feature | V1 | V2 (Recommended) |
|---|---|---|
| Runtime | Cloud Functions (1st gen) | Cloud Run |
| Concurrency | 1 request per instance | Up to 1000 concurrent requests per instance |
| Timeout | 9 minutes | 60 minutes (HTTP) |
| Min instances | Yes | Yes (with idle billing) |
| Traffic splitting | No | Yes (canary deployments) |

Use V2 for new functions. The concurrency model alone makes it significantly more efficient — a single instance can handle 1000 concurrent requests instead of needing 1000 instances.

**Cold starts:** Similar to Lambda (200ms-2s for Node.js). Mitigate with `minInstances`:
```javascript
exports.api = onRequest({ minInstances: 1, memory: '512MiB' }, handler);
```

**Environment configuration:**
```bash
# Set environment variables
firebase functions:config:set stripe.key="sk_live_abc123"

# V2 functions use parameterized config
# In code:
const { defineString } = require('firebase-functions/params');
const stripeKey = defineString('STRIPE_KEY');
```

```bash
# Deploy functions
firebase deploy --only functions

# Deploy a specific function
firebase deploy --only functions:onNewOrder

# View logs
firebase functions:log --only onNewOrder
```

### 2.5 Hosting

**What it is:** Fast, secure static web hosting with global CDN. Supports dynamic content via Cloud Functions or Cloud Run.

**Key features:**
- Automatic SSL certificates
- Atomic deploys with instant rollback
- Preview channels for PR previews
- Custom domain support
- Integration with GitHub Actions for CI/CD

```json
// firebase.json
{
  "hosting": {
    "public": "dist",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [
      {
        "source": "/api/**",
        "function": "api"
      },
      {
        "source": "**",
        "destination": "/index.html"
      }
    ],
    "headers": [
      {
        "source": "**/*.@(jpg|jpeg|gif|png|svg|webp)",
        "headers": [{ "key": "Cache-Control", "value": "max-age=31536000" }]
      }
    ]
  }
}
```

```bash
# Deploy
firebase deploy --only hosting

# Create a preview channel (great for PR previews)
firebase hosting:channel:deploy pr-123 --expires 7d

# Rollback to previous release
firebase hosting:rollback
```

**Pricing:** Free tier: 10 GB storage, 360 MB/day transfer. Paid: $0.026/GB storage, $0.15/GB transfer.

### 2.6 Storage

**What it is:** File storage backed by Google Cloud Storage. Upload and serve user-generated content with security rules.

```javascript
import { getStorage, ref, uploadBytes, getDownloadURL } from 'firebase/storage';

const storage = getStorage();

// Upload a file
const storageRef = ref(storage, `uploads/${userId}/${file.name}`);
const snapshot = await uploadBytes(storageRef, file, {
  contentType: file.type,
  customMetadata: { uploadedBy: userId }
});

// Get download URL (long-lived, includes access token)
const url = await getDownloadURL(snapshot.ref);
```

**Security rules for storage:**
```
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /uploads/{userId}/{fileName} {
      allow read: if request.auth != null;
      allow write: if request.auth.uid == userId
                   && request.resource.size < 10 * 1024 * 1024  // 10 MB max
                   && request.resource.contentType.matches('image/.*');
    }
  }
}
```

**Image resizing:** Use the `Resize Images` Firebase Extension to automatically generate thumbnails when images are uploaded.

---

## 3. FIREBASE SECURITY RULES

### 3.1 Firestore Rules Deep Dive

Security rules are the most critical and most commonly misconfigured part of Firebase. The reason is subtle: in a traditional backend, you write authorization logic in your server code, which you control. In Firebase, clients talk directly to the database, and rules are the only thing between your data and the world. Getting them wrong isn't a code smell — it's a data breach.

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Helper function: check if user is authenticated
    function isAuthenticated() {
      return request.auth != null;
    }

    // Helper function: check if user owns the document
    function isOwner(userId) {
      return request.auth.uid == userId;
    }

    // Helper function: check custom claim
    function hasRole(role) {
      return request.auth.token[role] == true;
    }

    // Helper function: validate required fields exist
    function hasRequiredFields(fields) {
      return request.resource.data.keys().hasAll(fields);
    }

    // Users collection: owner-only access
    match /users/{userId} {
      allow read: if isAuthenticated() && isOwner(userId);
      allow create: if isAuthenticated() && isOwner(userId)
                    && hasRequiredFields(['name', 'email'])
                    && request.resource.data.name is string
                    && request.resource.data.name.size() <= 100;
      allow update: if isAuthenticated() && isOwner(userId)
                    && !request.resource.data.diff(resource.data).affectedKeys()
                       .hasAny(['createdAt', 'uid']);  // Cannot modify immutable fields
      allow delete: if false;  // Users cannot delete their own account via client
    }

    // Organizations: role-based access
    match /organizations/{orgId} {
      allow read: if isAuthenticated()
                  && exists(/databases/$(database)/documents/organizations/$(orgId)/members/$(request.auth.uid));

      allow update: if isAuthenticated()
                    && get(/databases/$(database)/documents/organizations/$(orgId)/members/$(request.auth.uid)).data.role == 'admin';

      // Members subcollection
      match /members/{memberId} {
        allow read: if isAuthenticated()
                    && exists(/databases/$(database)/documents/organizations/$(orgId)/members/$(request.auth.uid));
        allow write: if isAuthenticated()
                     && get(/databases/$(database)/documents/organizations/$(orgId)/members/$(request.auth.uid)).data.role == 'admin';
      }
    }

    // Public posts: anyone can read, only author can write
    match /posts/{postId} {
      allow read: if true;
      allow create: if isAuthenticated()
                    && request.resource.data.authorId == request.auth.uid
                    && request.resource.data.createdAt == request.time;
      allow update: if isAuthenticated()
                    && resource.data.authorId == request.auth.uid
                    && request.resource.data.authorId == resource.data.authorId;  // Cannot change author
      allow delete: if isAuthenticated()
                    && resource.data.authorId == request.auth.uid;
    }
  }
}
```

### 3.2 Common Security Mistakes

1. **Open rules in production:** `allow read, write: if true;` -- this is the default for development mode. Never deploy this.

2. **Only checking auth, not ownership:**
   ```
   // BAD: Any authenticated user can read any user's data
   allow read: if request.auth != null;

   // GOOD: Only the document owner can read their data
   allow read: if request.auth.uid == userId;
   ```

3. **Not validating write data:** Clients can send arbitrary fields. Always validate shape, types, and values.

4. **Forgetting `get()` costs reads:** Each `get()` or `exists()` call in rules costs one document read. Use sparingly.

5. **Not testing rules:** Rules bugs are security vulnerabilities. Every rule should have a test.

### 3.3 Testing Rules with Firebase Emulator

```bash
# Start the emulator suite
firebase emulators:start

# Run rules unit tests
firebase emulators:exec "npm test"
```

```javascript
// rules.test.js
const { initializeTestEnvironment, assertSucceeds, assertFails } = require('@firebase/rules-unit-testing');

let testEnv;
beforeAll(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: 'test-project',
    firestore: { rules: fs.readFileSync('firestore.rules', 'utf8') }
  });
});

afterAll(() => testEnv.cleanup());

test('users can only read their own profile', async () => {
  const alice = testEnv.authenticatedContext('alice');
  const bob = testEnv.authenticatedContext('bob');

  // Alice can read her own profile
  await assertSucceeds(alice.firestore().doc('users/alice').get());

  // Bob cannot read Alice's profile
  await assertFails(bob.firestore().doc('users/alice').get());
});

test('unauthenticated users cannot read profiles', async () => {
  const unauth = testEnv.unauthenticatedContext();
  await assertFails(unauth.firestore().doc('users/alice').get());
});
```

---

## 4. FIREBASE + MODERN FRAMEWORKS

### 4.1 Firebase with Next.js

The key challenge: Firebase Client SDK runs on the browser. Firebase Admin SDK runs on the server. Never use the Admin SDK on the client (it bypasses security rules and exposes service account credentials).

This architecture boundary matters more than it might seem. The client SDK respects your security rules — it's constrained by them by design. The Admin SDK bypasses all of them — it has root access. Mixing them up is the kind of mistake that results in all your users' data being readable by anyone who reads your JavaScript bundle.

**Architecture:**
```
Browser (Client SDK)          Server (Admin SDK)
├── Auth state listener       ├── Verify ID tokens
├── Firestore queries         ├── Server-side Firestore queries (bypasses rules)
├── Real-time listeners       ├── API routes / Server Actions
└── Storage uploads           └── Server Components (data fetching)
```

**Server-side setup (Admin SDK):**
```javascript
// lib/firebase-admin.ts
import { getApps, initializeApp, cert } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';

if (!getApps().length) {
  initializeApp({
    credential: cert({
      projectId: process.env.FIREBASE_PROJECT_ID,
      clientEmail: process.env.FIREBASE_CLIENT_EMAIL,
      privateKey: process.env.FIREBASE_PRIVATE_KEY?.replace(/\\n/g, '\n'),
    }),
  });
}

export const adminAuth = getAuth();
export const adminDb = getFirestore();
```

**Client-side setup:**
```javascript
// lib/firebase.ts
import { initializeApp, getApps } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

const app = !getApps().length ? initializeApp(firebaseConfig) : getApps()[0];
export const auth = getAuth(app);
export const db = getFirestore(app);
```

**Server Component using Admin SDK:**
```javascript
// app/dashboard/page.tsx (Server Component)
import { adminDb } from '@/lib/firebase-admin';
import { cookies } from 'next/headers';

export default async function DashboardPage() {
  const sessionCookie = cookies().get('session')?.value;
  if (!sessionCookie) redirect('/login');

  const decoded = await adminAuth.verifySessionCookie(sessionCookie);
  const ordersSnap = await adminDb
    .collection('orders')
    .where('userId', '==', decoded.uid)
    .orderBy('createdAt', 'desc')
    .limit(20)
    .get();

  const orders = ordersSnap.docs.map(doc => ({ id: doc.id, ...doc.data() }));

  return <OrderList orders={orders} />;
}
```

### 4.2 Firebase with React Native / Expo

Use `@react-native-firebase/app` for native modules (better performance, offline support) or the JS SDK for Expo Go compatibility.

```javascript
// With @react-native-firebase (recommended for production)
import auth from '@react-native-firebase/auth';
import firestore from '@react-native-firebase/firestore';

// Sign in
await auth().signInWithEmailAndPassword(email, password);

// Firestore query with real-time listener
useEffect(() => {
  const unsubscribe = firestore()
    .collection('messages')
    .where('chatId', '==', chatId)
    .orderBy('createdAt', 'desc')
    .limit(50)
    .onSnapshot(snapshot => {
      const messages = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      setMessages(messages);
    });
  return unsubscribe;
}, [chatId]);
```

### 4.3 Firebase Admin SDK

Available for **Node.js**, **Python**, **Go**, and **Java**.

```python
# Python Admin SDK
import firebase_admin
from firebase_admin import credentials, firestore, auth

cred = credentials.Certificate('service-account.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

# Verify ID token
decoded = auth.verify_id_token(id_token)
uid = decoded['uid']

# Firestore operations (bypasses security rules)
doc_ref = db.collection('users').document(uid)
doc_ref.set({'name': 'Alice', 'updatedAt': firestore.SERVER_TIMESTAMP})

# Batch writes
batch = db.batch()
for item in items:
    ref = db.collection('items').document(item['id'])
    batch.set(ref, item)
batch.commit()  # Atomic: all or nothing (max 500 operations)
```

---

## 5. SCALING FIREBASE

### 5.1 Firestore Limitations

Every database has limits. Firestore's limits are worth knowing upfront, not after you've hit them in production at 2 AM:

| Limit | Value | Impact |
|---|---|---|
| Max document size | 1 MB | Store large blobs in Storage, not Firestore |
| Max fields per document | 40,000 | Rarely hit unless storing arrays of objects |
| Max writes per document per second | 1 | **This is the critical bottleneck** |
| Max writes per database per second | 10,000 (default) | Can be increased by contacting Google |
| Max `in` clause values | 30 | Split queries if you need more |
| Max composite indexes per database | 200 | Plan indexes carefully |

The 1-write-per-second-per-document limit is the one that surprises teams. A global counter in a single document, a leaderboard updated on every game action, a popular post with a like counter — all of these will hit this limit the moment you get real traffic.

### 5.2 Distributed Counters

The 1-write-per-document-per-second limit means you cannot have a popular counter in a single document. Solution: shard the counter across N documents.

```javascript
// Initialize counter with 10 shards
async function initCounter(docRef, numShards) {
  const batch = writeBatch(db);
  for (let i = 0; i < numShards; i++) {
    batch.set(doc(docRef, 'shards', `${i}`), { count: 0 });
  }
  await batch.commit();
}

// Increment: pick a random shard
async function incrementCounter(docRef, numShards) {
  const shardId = Math.floor(Math.random() * numShards);
  const shardRef = doc(docRef, 'shards', `${shardId}`);
  await updateDoc(shardRef, { count: increment(1) });
}

// Read: sum all shards
async function getCount(docRef) {
  const shards = await getDocs(collection(docRef, 'shards'));
  let total = 0;
  shards.forEach(snap => { total += snap.data().count; });
  return total;
}
```

With 10 shards, you can handle 10 writes/second. With 100 shards, 100 writes/second. Trade-off: reads become more expensive (N reads to get the count).

### 5.3 Data Modeling Patterns

**Denormalization:** Duplicate data to avoid joins (Firestore has no joins). When you display an order with the customer name, store the name in the order document instead of looking up the user document.

```javascript
// Instead of:  { userId: "u123" }  + separate lookup
// Store:       { userId: "u123", userName: "Alice", userAvatar: "https://..." }
```

Trade-off: Updates require fan-out writes. Use Cloud Functions to propagate changes:
```javascript
exports.onUserUpdate = onDocumentUpdated('users/{userId}', async (event) => {
  const { name, avatar } = event.data.after.data();
  const orders = await adminDb.collection('orders')
    .where('userId', '==', event.params.userId).get();

  const batch = adminDb.batch();
  orders.forEach(doc => {
    batch.update(doc.ref, { userName: name, userAvatar: avatar });
  });
  await batch.commit();
});
```

**Subcollections vs root collections:**
- **Subcollections** (e.g., `users/{userId}/orders`): Natural hierarchy, queries scoped to parent, good for per-user data. Cannot easily query across all users' orders without collection group queries.
- **Root collections** (e.g., `orders` with `userId` field): Flat structure, easy cross-user queries, simpler security rules. Better for data accessed across multiple parents.

**Rule of thumb:** If you primarily query within a single parent (e.g., "get this user's orders"), use subcollections. If you need cross-parent queries (e.g., "get all pending orders"), use root collections.

### 5.4 When to Move Beyond Firebase

**Signs you have outgrown Firebase:**
- Monthly bill exceeds what equivalent infrastructure would cost on AWS/GCP
- You need complex queries (aggregations, joins, full-text search) that Firestore does not support natively
- The 1 write/sec/document limit is causing contention despite sharding
- You need multi-tenancy with strong data isolation
- You need relational data modeling with complex transactions
- Compliance requirements mandate infrastructure you control

This is a normal part of a product's evolution. Firebase is optimized for getting to product-market fit. AWS is optimized for operating at scale. The best teams use Firebase to learn what they're building, then migrate the parts that need more power when they need them — not before.

**Migration paths:**
- **Firebase Auth -> AWS Cognito or Auth0:** Export users with `admin.auth().listUsers()`, import to new system, update tokens on client
- **Firestore -> PostgreSQL:** Export via `gcloud firestore export`, transform documents to relational schema
- **Firestore -> DynamoDB:** Document model maps more naturally. Export and transform PK/SK design
- **Cloud Functions -> AWS Lambda:** Rewrite triggers. Firebase-specific triggers (Firestore, Auth) need equivalent event sources
- **Firebase Hosting -> Vercel/AWS CloudFront + S3:** Straightforward static asset migration

**Gradual migration pattern:** Keep Firebase Auth (it is the hardest to migrate), move the database and backend to AWS/GCP. Firebase Auth works with any backend -- just verify ID tokens server-side. This way you migrate the database and compute at your own pace without forcing all your users to re-authenticate.

---

## 6. FIREBASE VS AWS COMPARISON

### 6.1 Feature-by-Feature Comparison

| Feature | Firebase | AWS Equivalent | Notes |
|---|---|---|---|
| Authentication | Firebase Auth | Cognito | Firebase Auth has simpler setup and more providers OOTB |
| Document Database | Firestore | DynamoDB | Firestore has real-time sync built in; DynamoDB is more scalable |
| Relational Database | None | RDS/Aurora | Firebase has no relational option |
| Real-time Database | Realtime Database | AppSync + DynamoDB | Firebase is simpler; AppSync is more flexible |
| Serverless Functions | Cloud Functions | Lambda | Lambda has more runtimes, better scaling, richer event sources |
| Object Storage | Cloud Storage | S3 | S3 is cheaper and more feature-rich at scale |
| CDN/Hosting | Firebase Hosting | CloudFront + S3 | Firebase is simpler; CloudFront is more configurable |
| Push Notifications | Cloud Messaging (FCM) | SNS / Pinpoint | FCM is the industry standard for mobile push |
| Analytics | Google Analytics | Pinpoint / custom | Firebase Analytics is free and powerful for mobile |
| Crash Reporting | Crashlytics | None (use Sentry) | Crashlytics is best-in-class for mobile |
| ML | ML Kit | SageMaker / Rekognition | Different scope: on-device (ML Kit) vs cloud (SageMaker) |
| Full-text Search | None | OpenSearch | Firebase requires third-party (Algolia, Typesense) |
| Message Queues | Pub/Sub (GCP) | SQS/SNS/EventBridge | No native Firebase queue; must use GCP Pub/Sub |

### 6.2 When to Use Firebase

- **Rapid prototyping:** Get a full backend running in hours, not days
- **Real-time applications:** Chat, collaboration, live dashboards (Firestore real-time listeners are unmatched)
- **Mobile-first products:** Best-in-class mobile SDKs, offline persistence, push notifications, analytics, crash reporting
- **Small teams (1-5 engineers):** Minimal backend code, managed infrastructure, generous free tier
- **MVPs and startups:** Ship fast, validate the idea, migrate later if needed

### 6.3 When to Use AWS

- **Enterprise applications:** Complex compliance (HIPAA, SOC2, PCI), VPC isolation, fine-grained IAM
- **Complex backends:** Relational data, complex queries, multi-service architectures, custom middleware
- **Cost optimization at scale:** Firebase costs grow linearly with usage. AWS offers reserved pricing, spot instances, and more pricing levers
- **High-throughput workloads:** DynamoDB scales far beyond Firestore limits. Lambda handles millions of concurrent invocations
- **ML/AI workloads:** SageMaker, Bedrock, GPU instances -- AWS has the deepest ML infrastructure

See Chapter 31 for the GCP angle: when your team is already Google-native, Firebase + GCP is a coherent stack where Firebase provides the developer experience and GCP provides the escape hatch when you need raw infrastructure.

### 6.4 Hybrid Patterns

The most elegant architectures often use both. Firebase for the parts it does brilliantly (real-time, mobile, auth), AWS for the parts it does brilliantly (scale, compliance, compute).

**Firebase Auth + AWS Backend:**
The most common hybrid pattern. Firebase Auth handles sign-up/sign-in. Your AWS backend verifies Firebase ID tokens:

```javascript
// AWS Lambda verifier
const admin = require('firebase-admin');
admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });

exports.handler = async (event) => {
  const token = event.headers.authorization?.split('Bearer ')[1];
  try {
    const decoded = await admin.auth().verifyIdToken(token);
    // decoded.uid, decoded.email available
    // Query DynamoDB, RDS, etc.
    return { statusCode: 200, body: JSON.stringify(data) };
  } catch (error) {
    return { statusCode: 401, body: JSON.stringify({ error: 'Unauthorized' }) };
  }
};
```

This pattern is useful because Firebase Auth is genuinely hard to replace. It handles OAuth provider integrations, token refresh, session management, and device-specific quirks (especially on iOS and Android). Once your users are in Firebase Auth, migrating them to a different auth system requires either a forced re-login or a careful token migration. Keeping Firebase Auth while moving your data layer to AWS/DynamoDB/RDS is often the smoothest path forward.

**Firebase Hosting + AWS Lambda:**
Use Firebase Hosting as your CDN/static host. API calls go to API Gateway + Lambda:
```json
// firebase.json
{
  "hosting": {
    "public": "dist",
    "rewrites": [
      { "source": "/api/**", "run": { "serviceId": "api" } },
      { "source": "**", "destination": "/index.html" }
    ]
  }
}
```
Or simply call your AWS API Gateway URL directly from the client (configure CORS).

**Firestore for real-time + DynamoDB for analytics:**
Use Firestore for user-facing real-time features (chat, presence, live updates). Stream changes to DynamoDB via Cloud Functions for analytics queries and reporting that need DynamoDB's query flexibility.

---

## QUICK REFERENCE: FIREBASE CLI CHEAT SHEET

```bash
# Project management
firebase projects:list
firebase use --add                              # Add a project alias
firebase use production                         # Switch to production

# Emulators (local development)
firebase emulators:start                        # Start all emulators
firebase emulators:start --only firestore,auth  # Start specific emulators
firebase emulators:export ./seed-data           # Export emulator data
firebase emulators:start --import ./seed-data   # Import seed data on start

# Deployment
firebase deploy                                 # Deploy everything
firebase deploy --only hosting                  # Deploy only hosting
firebase deploy --only functions:myFunction     # Deploy single function
firebase deploy --only firestore:rules          # Deploy Firestore rules
firebase deploy --only firestore:indexes        # Deploy Firestore indexes

# Functions
firebase functions:log                          # View function logs
firebase functions:delete myFunction            # Delete a function
firebase functions:shell                        # Interactive function testing

# Hosting
firebase hosting:channel:deploy preview-123     # Deploy to preview channel
firebase hosting:channel:list                   # List preview channels
firebase hosting:rollback                       # Rollback last deploy

# Firestore
firebase firestore:delete --all-collections     # Delete all data (careful!)
firebase firestore:indexes                      # List indexes
```

---

## Try It Yourself

Want to put this into practice? The [TicketPulse course](../course/) has hands-on modules that build on these concepts:

- **[L2-M44: Terraform & Infrastructure as Code](../course/modules/loop-2/L2-M44-terraform-and-iac.md)** — Replace click-ops with Terraform modules for TicketPulse's Firebase infrastructure
- **[L3-M62: Cloud Provider Deep Dive](../course/modules/loop-3/L3-M62-cloud-provider-deep-dive.md)** — Go beyond the basics: Firestore security rules at production scale

### Quick Exercises

1. **Set up a Firebase project with Firestore security rules** — create a project, define rules for a users collection with owner-only access, and test them with the Firebase Emulator.
2. **Build a real-time listener** — create a simple Firestore collection, add a real-time listener on the client, and verify that changes propagate instantly to all connected clients.
3. **Compare Firestore and DynamoDB pricing for your workload** — estimate your read/write volume and compare what the monthly bill would look like on each platform.

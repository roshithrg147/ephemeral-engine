# Ephemeral Engine — Authentication Gateway Documentation

This document describes the Phase 1 & Phase 2 Authentication Gateway design, runtime configuration, session persistence policy, and operational safety model.

---

## 1. Architecture Overview

Ephemeral Engine enforces a strict two-tier security model:

1. **Identity Provider (Frontend / Browser)**:
   - **Firebase Authentication** (`ephemeralai-a8bee`) authenticates browser identity using Google OAuth 2.0 / OIDC.
   - The browser obtains genuine Firebase ID tokens signed by Google.
   - Firebase Authentication is strictly an identity provider, not an authorization authority.

2. **Authoritative Access Engine (Backend / PostgreSQL)**:
   - **FastAPI** verifies the incoming Firebase ID token (issuer, audience, signature) using PyJWT and JWKS / Firebase Admin.
   - **PostgreSQL** is the sole authoritative store for application users (`users`), tenants (`tenants`), active memberships (`tenant_memberships`), and permission roles (`viewer`, `operator`, `admin`).
   - FastAPI constructs an internal `Principal` only after resolving the `firebase_uid` against PostgreSQL.

---

## 2. Environment Variables & Runtime Boundary

### Frontend Environment Variables (`engine-dashboard/.env.example`)

```env
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=ephemeralai-a8bee
VITE_FIREBASE_APP_ID=
VITE_FIREBASE_MESSAGING_SENDER_ID=
VITE_API_BASE_URL=/api
```

### Safety Rules

- **Client Configuration is Public**: `VITE_FIREBASE_*` values are compiled into the browser bundle. Never place Firebase Admin credentials, service account JSON keys, or private keys in the frontend repository or build output.
- **Fail-Fast Boundary**: The frontend runtime boundary (`config.ts`) validates required variables upon application launch. Missing or blank values put the app into an explicit `error` state before rendering protected dashboard content. Placeholder values in production builds fail closed immediately.

---

## 3. Session Persistence Policy

- **Default Persistence**: `browserSessionPersistence` (Firebase Auth session persistence).
- Tokens persist for the current browser session/tab window and are invalidated upon browser close or explicit sign-out.
- **No Application Token Storage**: Application code **never** writes Firebase ID tokens to `localStorage` or `sessionStorage`. ID tokens are fetched dynamically via `auth.currentUser.getIdToken()`.

---

## 4. Google Sign-In & Admission Flow

1. **Google Sign-In Popup**:
   - The user clicks **Sign in with Google** on the login page (`Login.tsx`).
   - The application invokes `signInWithPopup(auth, googleProvider)`.
   - Only basic identity scopes (`openid`, `profile`, `email`) are requested.

2. **PostgreSQL Application Admission Check**:
   - After Firebase authentication succeeds, `AuthContext` performs an initial backend check (`GET /api/session/list`) with `Authorization: Bearer <idToken>`.
   - If PostgreSQL resolves an active user and active tenant membership, the dashboard transitions to `authenticated`.
   - If the identity is verified by Google but not provisioned/active in PostgreSQL, the backend returns `403 Forbidden`. The dashboard displays an **Access Denied (403)** error screen. The user is **not** automatically signed out of Firebase, allowing clear feedback that access has not been provisioned.

---

## 5. HTTP Error Semantics (401 vs 403)

| Status | Meaning | System Action |
| :--- | :--- | :--- |
| **401 Unauthorized** | Token missing, expired, or invalid signature. | For idempotent requests (`GET`/`HEAD`), `customFetch` attempts 1 forced token refresh (`getIdToken(true)`) and retries once. If the second attempt fails, triggers Firebase `signOut(auth)` and returns to `/login`. |
| **403 Forbidden** | Valid identity, but account not admitted in PostgreSQL or lacks required permission. | Preserves Firebase auth state, displays a safe access-denied error banner, and does **not** auto sign-out. |

---

## 6. Authenticated SSE Streaming

- Query streams (`POST /api/agent/query`) attach `Authorization: Bearer <idToken>` and `Accept: text/event-stream` via `fetch`.
- Tokens are **never** passed in URL query parameters.
- In the event of a stream interruption, reconnection retrieves a fresh ID token and reconciles session state without duplicating generation requests.

---

## 7. Logout & Cleanup Semantics

When the user clicks **Sign Out**:

1. Aborts all pending API fetch requests and SSE streams (`AbortController`).
2. Flushes sensitive in-memory session buffers.
3. Removes obsolete local storage token keys (`sc-evm-auth-token`).
4. Invokes `await signOut(auth)`.
5. Transitions state to `unauthenticated` and redirects to `/login`.

*Note: Sign-out clears the browser session state. Burning a session remains a separate, authorized backend operation (`DELETE /api/session/burn/{id}`).*

---

## 8. Deployment Prerequisites

Before deploying the dashboard to a production hostname:

1. Add the deployment domain (e.g. `dashboard.example.com`) to **Firebase Console -> Authentication -> Settings -> Authorized Domains**.
2. Configure environment variables (`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, etc.) in the build pipeline.

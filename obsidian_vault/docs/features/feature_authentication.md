---
created: 2026-11-09
updated: 2026-11-10
type: spec
phase: 7
layer: application
status: implemented
tags: [authentication, security, session-management, clean-architecture, argon2id, jwt, rate-limiting, postgresql, sqlite]
category: meta-project
---

# Feature Specification: Authentication, Authorization & User Management (Phase 7)

## 1. Overview & Business Value

This specification defines the authentication and user lifecycle architecture for **ATENEA** (Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas), providing secure multi-user access control, credential management, per-user data isolation, and administration capabilities for both local homelab environments and multi-tenant corporate deployments.

### Core Capabilities
1. **Initial Bootstrap Wizard (`/setup`):** On first run, a dedicated wizard guides the operator through creating the root administrator. Protected by configurable bootstrap tokens (`INITIAL_SETUP_TOKEN`) and sliding-window rate limiting to prevent setup hijacking.
2. **Cryptographic Identity Protection:** OWASP-compliant password hashing with Argon2id ($m=64\text{ MiB}, t=2, p=2$) executed off the event loop via worker threads, with dummy verification against user-enumeration timing attacks.
3. **Stateless JWT Sessions with Active Revocation:** HS256 tokens stored strictly in `HttpOnly`, `SameSite=Lax` cookies, containing cryptographic claims (`iss`, `aud`, `jti`, `token_version`). Validated against database state on every HTTP request and WebSocket handshake. Password resets immediately increment `token_version`, revoking all active JWTs.
4. **Fail-Closed WebSocket Defense:** Real-time endpoints (`/ws/debate` and `/ws/audio/wake-word`) mandate authentication, Origin (CSWSH) verification, and fail-closed termination (1008/1011) if uninitialized or unauthorized.
5. **Configurable Deletion Strategies:** Environment-controlled user deletion via `AUTH_DELETE_STRATEGY` (`soft` with `deleted_at` audit timestamps vs `hard` with cascade purging of debates and custom agent model configurations).
6. **Dual Database Composition Root:** Zero-configuration SQLite for homelab appliances with seamless auto-migration, and asynchronous connection pooling via PostgreSQL (`asyncpg`) for enterprise infrastructure.

---

## 2. Architecture & Clean Architecture Compliance

Adhering strictly to Clean Architecture (ADR-004), authentication logic resides in the Application and Domain layers, completely agnostic of HTTP transports or database engines.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Presentation Layer                            │
│  - FastAPI Routes: /api/auth/{status, setup, login, logout, me, users} │
│  - Sliding-Window Rate Limiter Middleware (429 Too Many Requests)      │
│  - Dependencies: get_current_user, require_admin, authenticate_ws      │
│  - WebSocket Handshake CSWSH & Fail-Closed Guards                      │
│  - Vue 3: AppHeader Operator Menu, LoginView, InitialSetupView, Modal  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ calls
┌───────────────────────────────────▼────────────────────────────────────┐
│                           Application Layer                            │
│  - AuthService: Coordinates authentication, token generation,          │
│    self-service password changes, user lifecycle, and cascade purges   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ depends on Ports
┌───────────────────────────────────▼────────────────────────────────────┐
│                             Domain Layer                               │
│  - Entities: User (immutable, NFKC validated, token_version)           │
│  - Exceptions: SelfModificationError, LastAdminError, WeakPasswordError│
│  - Ports: IUserRepository, IPasswordHasher, ITokenService              │
│    IDebateRepository, IAgentConfigRepository                           │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │ implements
┌───────────────────────────────────┴────────────────────────────────────┐
│                         Infrastructure Layer                           │
│  - Argon2idPasswordHasher (argon2-cffi)                                │
│  - JwtTokenService (PyJWT with HS256, fail-fast key validation)        │
│  - SQLiteUserRepository & PostgreSQLUserRepository                     │
│  - SqliteDebateRepository (scoped user_id with legacy auto-assignment)  │
│  - SqliteAgentConfigRepository (user-scoped agent models)              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Threat Model & Security Posture

| Threat Vector | Mitigation Strategy | Implemented Component |
|---|---|---|
| **Brute Force & Online DoS** | In-memory sliding-window log limiting login (5/min) and setup (3/min). Exceeding limits returns HTTP 429 with `Retry-After: 60`. | `src/presentation/api/dependencies/rate_limiter.py` |
| **Weak JWT Secret Keys** | Fail-fast validation at startup rejecting known default strings and keys $< 32$ bytes long. | `src/infrastructure/security/jwt_token_service.py` |
| **WebSocket Hijacking (CSWSH)** | Validates `Origin` header against CORS configuration during handshake. | `validate_websocket_origin` in `dependencies/auth.py` |
| **Fail-Open LLM Quota Consumption** | If system has 0 users (`is_initialized == False`), WebSockets close immediately with code `1008 ("System setup not completed")`. | `authenticate_websocket` in `dependencies/auth.py` |
| **Timing Attacks & User Enumeration** | Fixed dummy Argon2id hash with identical parameters run on non-existent users. | `_DUMMY_HASH` in `AuthService.authenticate` |
| **Homoglyph & Unicode Spoofing** | Usernames normalized via NFKC Unicode standard and validated by alphanumeric regex `^[a-zA-Z0-9_\-\.]{3,50}$`. | `User.__post_init__` in `src/domain/entities/user.py` |
| **Stale JWT / Revocation Leak** | `token_version` stored on user entity and encoded in JWT claims. Password changes increment `token_version`, instantly invalidating active sessions. | `AuthService.validate_token` |
| **Cross-Site Request Forgery (CSRF)** | Cookies configured with `SameSite=Lax`. Mutating endpoints enforce origin validation against trusted hostnames. | `_set_auth_cookie` in `routes/auth.py` |

---

## 4. API Specification

### REST Endpoints (`/api/auth`)

| Method | Endpoint | Access | Description | Success | Error Codes |
|---|---|---|---|---|---|
| `GET` | `/status` | Public | Returns initialization and authentication state. | `200 OK` | — |
| `POST` | `/setup` | Public (rate-limited) | Initializes first administrator (accepts optional `setup_token`). | `200 OK` | `400`, `403`, `429` |
| `POST` | `/login` | Public (rate-limited) | Authenticates credentials and sets session cookie. | `200 OK` | `401`, `403`, `429` |
| `POST` | `/logout` | Public | Clears session cookie. | `200 OK` | — |
| `GET` | `/me` | Authenticated | Returns current authenticated user profile. | `200 OK` | `401` |
| `POST` | `/change-password` | Authenticated | Allows user to update own password and refresh session. | `200 OK` | `400`, `401` |
| `GET` | `/users` | Admin Only | Lists all registered users. | `200 OK` | `401`, `403` |
| `POST` | `/users` | Admin Only | Creates a new user account. | `200 OK` | `400`, `401`, `403`, `409` |
| `PATCH` | `/users/{id}` | Admin Only | Updates user status, role, or resets password. | `200 OK` | `400`, `401`, `403`, `404`, `409` |
| `DELETE` | `/users/{id}` | Admin Only | Deletes user (soft suspension vs hard purge). | `200 OK` | `400`, `401`, `403`, `404`, `409` |

---

## 5. Verification & Testing Matrix

- **Domain Entity Tests:** `backend/tests/domain/test_user_entity.py` (5/5 passed)
- **Application Service Tests:** `backend/tests/application/services/test_auth_service.py` (18/18 passed)
- **Persistence Layer Tests:**
  - `test_sqlite_user_repository.py` (7/7 passed)
  - `test_postgres_user_repository.py` (7/7 passed)
  - `test_sqlite_debate_repository.py` (6/6 passed)
  - `test_sqlite_debate_user_isolation.py` (2/2 passed)
- **Security & Infrastructure Tests:**
  - `test_argon2id_hasher.py` (4/4 passed)
  - `test_jwt_token_service.py` (4/4 passed)
- **Presentation & WebSockets Tests:**
  - `test_rate_limiter.py` (5/5 passed)
  - `test_composition_root.py` (3/3 passed)
  - `test_auth.py` (7/7 passed)
  - `test_debate_auth.py` (4/4 passed)
  - `test_wake_word.py` (6/6 passed)
  - `test_debate.py` (14/14 passed)
- **Frontend Unit & Component Tests:** `frontend/src/` (30 test suites, 286/286 passed)
- **Type Checking:** `vue-tsc --build` (0 errors)


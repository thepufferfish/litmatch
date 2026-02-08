# Implementation Plan: LitMatch React Frontend (SPEC.md)

## Requirements Summary

Replace the Streamlit frontend with a React SPA across 3 phases. Phase 1 is ~95% built already; this plan covers **audit/fixes for Phase 1**, **full implementation of Phase 2** (Auth & Ratings), and an **outline for Phase 3** (Recommendations).

---

## Phase 1 Audit: Results

The existing code was audited against every spec requirement. **Most items are already compliant:**

| Item | Status | Notes |
|------|--------|-------|
| Reviews returns `[]` not 404 | **Compliant** | Already returns empty list |
| Search validation (min 2 chars) | **Compliant** | `Query(min_length=2)` handles it (returns 422 not 400, but functionally correct) |
| Pagination (page 0 → 422) | **Compliant** | `Query(ge=1)` rejects 0/negative |
| Null field fallbacks | **Compliant** | All 6 fields handled per spec |
| Three distinct empty states | **Compliant** | Messages match spec exactly |
| Genre routes use slug | **Fix needed** | Currently uses `/genre/:id`, spec says `/genre/:slug` |
| MobileGenreSelect SPA nav | **Fix needed** | Uses `window.location.href` (full page reload) instead of React Router |
| SearchBar URL sync | **Fix needed** | State not synced on browser back/forward |

### Phase 1 Fixes (4 steps)

#### Step 1.1: Convert genre routes from `:id` to `:slug`

Create a slugify utility and resolve slug → genre ID client-side using `useGenres`.

**Files:**
- NEW: `frontend/src/utils/slugify.ts`
- MODIFY: `frontend/src/App.tsx` — route `/genre/:id` → `/genre/:slug`
- MODIFY: `frontend/src/pages/BrowsePage.tsx` — parse slug param, resolve to genre ID
- MODIFY: `frontend/src/components/GenreSidebar.tsx` — slug-based links
- MODIFY: `frontend/src/pages/BookDetailPage.tsx` — slug-based genre tag links

**Approach:**
1. Create `slugify(name: string): string` — lowercase, replace spaces with hyphens, remove non-alphanumeric except hyphens.
2. In `BrowsePage`, read `slug` param. Use genres list from `useGenres()` to find matching genre by `slugify(genre.name) === slug`. Extract `id` to pass to `useBooks`.
3. Update all `to={/genre/${genre.id}}` links to `to={/genre/${slugify(genre.name)}}`.
4. Handle edge case where slug matches no genre — show "Genre not found" or redirect to `/`.

**Dependencies:** None
**Risk:** Low

#### Step 1.2: Fix MobileGenreSelect to use React Router navigation

Replace `window.location.href` with `useNavigate()` from React Router.

**File:** `frontend/src/components/GenreSidebar.tsx` (lines 112-143)

```typescript
// Current (broken SPA):
window.location.href = "/";
window.location.href = `/genre/${val}`;

// Fixed:
const navigate = useNavigate();
navigate("/");
navigate(`/genre/${slugify(val)}`);
```

After Step 1.1, the `<option value>` should change from `genre.id` to `slugify(genre.name)`.

**Dependencies:** Step 1.1
**Risk:** Low

#### Step 1.3: Sync SearchBar value with URL state

Add a `useEffect` to keep internal state in sync with `initialValue` prop changes.

**File:** `frontend/src/components/SearchBar.tsx`

```typescript
useEffect(() => {
  setValue(initialValue);
}, [initialValue]);
```

This ensures browser back/forward navigation properly updates the search input.

**Dependencies:** None
**Risk:** Low

#### Step 1.4 (Optional): Explicit 400 for empty search query

If strict spec compliance is desired, change the search endpoint to return 400 instead of 422 for empty/short queries.

**File:** `backend/app/main.py`

```python
@app.get("/books/search", response_model=PaginatedResponse[Book])
def search_books(
    *,
    session=Depends(get_session),
    q: str = Query(default=""),  # Remove min_length, handle manually
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=24, ge=1, le=100),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query must not be empty")
    if len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")
    # ... rest of function
```

**Dependencies:** None
**Risk:** Low

---

## Phase 2: Auth & Ratings

### Phase 2A: Backend (8 steps)

#### Step 2A.1: Create configuration module

Centralize all config using environment variables. Require `SECRET_KEY` at startup.

**File (NEW):** `backend/app/config.py`

```python
import os

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable must be set")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://bookuser:bookpassword@localhost:5432/bookdb"
)

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")

REFRESH_COOKIE_PATH = os.environ.get("REFRESH_COOKIE_PATH", "/auth/refresh")
```

**Dependencies:** None
**Risk:** Medium — requires setting `SECRET_KEY` env var in all environments

#### Step 2A.2: Add dependencies to requirements.txt

**File:** `backend/requirements.txt`

Add:
```
python-jose[cryptography]>=3.3.0
slowapi>=0.1.9
```

**Dependencies:** None
**Risk:** Low

#### Step 2A.3: Add models for JWT refresh tokens and validation

**File:** `backend/db/models.py`

1. Add `RefreshToken` model:

```python
class RefreshToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='user.id')
    token_hash: str = Field(unique=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.now)
    user: User = Relationship(back_populates='refresh_tokens')
```

2. Add `refresh_tokens` relationship to `User`.

3. Add input validation to `UserCreate` (username: `^[a-zA-Z0-9_]{3,30}$`, password: 8+ chars with letter+digit).

4. Add `RatingCreate` schema (body: `{ book_id: int, rating: int }`; rating 1-5).

5. Add `AuthResponse` schema (`access_token`, `token_type`, `user: UserPublic`).

**Dependencies:** None
**Risk:** Medium — new table requires `create_all` run

#### Step 2A.4: Create auth module with JWT logic

**File (NEW):** `backend/app/auth.py`

Functions:
- `create_access_token(user_id, username)` — short-lived (15 min), contains `sub`, `username`, `exp`, `type`
- `create_refresh_token()` — cryptographically random via `secrets.token_urlsafe(64)`
- `hash_token(token)` — SHA-256 hash for storage (never store raw tokens)
- `decode_access_token(token)` — decode and validate, raise 401 on failure
- `get_current_user(credentials, session)` — FastAPI dependency extracting user from Bearer token
- `store_refresh_token(session, user_id, raw_token)` — store hashed token with expiry
- `validate_refresh_token(session, raw_token)` — verify hash exists and not expired
- `revoke_refresh_token(session, raw_token)` — delete token record (logout)

**Dependencies:** Steps 2A.1, 2A.2, 2A.3
**Risk:** Medium — JWT implementation must be correct for security

#### Step 2A.5: Create rate limiting module

**File (NEW):** `backend/app/rate_limit.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

**Dependencies:** Step 2A.2
**Risk:** Low

#### Step 2A.6: Refactor main.py — CORS, JWT auth, rate limiting

**File:** `backend/app/main.py`

This is the largest backend change. Sub-steps:

**6a. Add CORS middleware:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
```

**6b. Add rate limiter state and exception handler.**

**6c. Refactor `POST /auth/register`:**
- Hash password, create user
- Generate access token + refresh token
- Set httpOnly refresh cookie (`Secure`, `SameSite=Strict`, path from config)
- Return `AuthResponse` with access token + user info
- Rate limit: 3/min/IP
- Generic error: `"Registration failed"` (prevents user enumeration)

**6d. Refactor `POST /auth/login`:**
- Validate credentials
- Generate access token + refresh token
- Set httpOnly refresh cookie
- Return `AuthResponse`
- Rate limit: 5/min/IP
- Generic error: `"Invalid credentials"`

**6e. Add `POST /auth/refresh`:**
- Read refresh token from cookie
- Validate against database
- Rotate: revoke old token, issue new refresh + access tokens
- Set new httpOnly cookie
- Return `AuthResponse`

**6f. Add `POST /auth/logout`:**
- Revoke refresh token from database
- Clear refresh cookie
- Return `{"detail": "Logged out"}`

**6g. Protect `POST /ratings/`:**
- Add `Depends(get_current_user)`
- Accept `RatingCreate` body (just `book_id` + `rating`)
- Derive `user_id` from JWT, not request body
- Rate limit: 30/min/user

**Dependencies:** Steps 2A.1 through 2A.5
**Risk:** High — core auth refactoring

#### Step 2A.7: Update docker-compose and environment

**File:** `compose.yaml`

Add to backend service:
```yaml
environment:
  SECRET_KEY: ${SECRET_KEY}
  CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:5173}
```

**File:** `.env` (not committed)

Add:
```
SECRET_KEY=<generate-a-secure-random-key>
CORS_ORIGINS=http://localhost:5173
```

**Dependencies:** Step 2A.1
**Risk:** Low

#### Step 2A.8: Update Dockerfile

**File:** `backend/Dockerfile`

- Fix truncated filename reference on line 4
- Update Python version from 3.11 to 3.12 to match `.python-version`

**Dependencies:** Step 2A.2
**Risk:** Low

---

### Phase 2B: Frontend (12 steps)

#### Step 2B.1: Add auth-related TypeScript types

**File:** `frontend/src/types/index.ts`

```typescript
export interface UserPublic {
  id: number;
  username: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserPublic;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterCredentials {
  username: string;
  password: string;
}

export interface RatingCreate {
  book_id: number;
  rating: number;
}
```

**Dependencies:** None
**Risk:** Low

#### Step 2B.2: Create AuthContext

**File (NEW):** `frontend/src/context/AuthContext.tsx`

Design:
- Access token stored in `useRef` (not state, not localStorage) — lost on page refresh by design
- On mount, attempt silent refresh via `POST /auth/refresh` to restore session from httpOnly cookie
- Expose: `user`, `isAuthenticated`, `isLoading`, `login()`, `register()`, `logout()`, `getAccessToken()`

**Dependencies:** Step 2B.1
**Risk:** Medium

#### Step 2B.3: Update API client with auth interceptor

**File:** `frontend/src/api/client.ts`

Changes:
- Export `setAuthHelpers(getter, setter)` for AuthContext to register token access
- Add `withCredentials: true` to send httpOnly cookies
- Request interceptor: inject `Authorization: Bearer` header
- Response interceptor: on 401 (non-auth endpoints), attempt refresh with subscriber queue pattern
- Handle 429 rate limit errors with user-friendly messages

The 401 refresh queue pattern:
- First 401 triggers a refresh attempt
- Subsequent 401s during refresh are queued
- On successful refresh, all queued requests are retried with new token
- On failed refresh, all queued requests are rejected

**Dependencies:** Step 2B.2
**Risk:** High — refresh queue pattern is complex

#### Step 2B.4: Create LoginPage

**File (NEW):** `frontend/src/pages/LoginPage.tsx`

- Username and password fields
- Client-side validation matching backend rules
- Submit calls `auth.login()` from `useAuth()`
- On success, redirect to previous page or home
- On failure, error displayed via toast (handled by API client)
- Link to register page
- If already authenticated, redirect to home
- Warm bookstore aesthetic matching existing design

**Dependencies:** Steps 2B.2, 2B.11
**Risk:** Low

#### Step 2B.5: Create RegisterPage

**File (NEW):** `frontend/src/pages/RegisterPage.tsx`

- Username, password, and confirm password fields
- Validation: username `^[a-zA-Z0-9_]{3,30}$`, password 8+ chars with letter+digit, confirm must match
- Calls `auth.register()` on submit
- Otherwise same behavior as LoginPage

**Dependencies:** Steps 2B.2, 2B.11
**Risk:** Low

#### Step 2B.6: Create StarRating component

**File (NEW):** `frontend/src/components/StarRating.tsx`

```typescript
interface StarRatingProps {
  value: number;          // Current rating (0 if unrated)
  onChange?: (rating: number) => void;  // undefined = read-only
  disabled?: boolean;
}
```

- Five star icons (filled/outlined based on value)
- Hover state shows preview rating
- Click to select
- Gold/leather color for filled stars, parchment for empty
- Whole stars only (no half-stars)
- Read-only mode (no hover effects, no click handler)

**Dependencies:** None
**Risk:** Low

#### Step 2B.7: Create useRatings hook

**File (NEW):** `frontend/src/hooks/useRatings.ts`

- `useUserRating(bookId, userId)` — query for existing rating
- `useSubmitRating()` — mutation that invalidates rating query on success

**Dependencies:** Step 2B.1
**Risk:** Low

#### Step 2B.8: Add rating section to BookDetailPage

**File:** `frontend/src/pages/BookDetailPage.tsx`

Below critic reviews, add "Your Rating" section:
- **Authenticated:** Interactive `StarRating`, current rating display, optimistic update with rollback on error
- **Unauthenticated:** "Log in to rate this book" link to `/login`

**Dependencies:** Steps 2B.2, 2B.6, 2B.7
**Risk:** Medium — optimistic update logic

#### Step 2B.9: Update App.tsx with AuthProvider and new routes

**File:** `frontend/src/App.tsx`

1. Wrap app in `<AuthProvider>`
2. Add routes: `/login` → `LoginPage`, `/register` → `RegisterPage`
3. Update `Header` component:
   - Not authenticated: "Log in" and "Sign up" links
   - Authenticated: Username display and "Log out" button

**Dependencies:** Steps 2B.2, 2B.4, 2B.5
**Risk:** Low

#### Step 2B.10: Connect AuthContext to API client

In `AuthProvider`, call `setAuthHelpers` from the API client on mount so the interceptor can access the token.

**File:** `frontend/src/context/AuthContext.tsx`

```typescript
import { setAuthHelpers } from '@/api/client';

// Inside AuthProvider:
useEffect(() => {
  setAuthHelpers(
    () => accessTokenRef.current,
    (token: string) => { accessTokenRef.current = token; }
  );
}, []);
```

**Dependencies:** Steps 2B.2, 2B.3
**Risk:** Low

#### Step 2B.11: Create form validation utility

**File (NEW):** `frontend/src/utils/validation.ts`

```typescript
export function validateUsername(username: string): string | null;
export function validatePassword(password: string): string | null;
```

Shared by LoginPage and RegisterPage. Rules match backend validators.

**Dependencies:** None
**Risk:** Low

#### Step 2B.12: Fix Vite proxy cookie path

The Vite dev proxy rewrites `/api/auth/refresh` → `/auth/refresh` on the backend, but the browser sees the URL as `/api/auth/refresh`. A cookie set with `path="/auth/refresh"` won't be sent by the browser for `/api/auth/refresh`.

**Fix:** Make cookie path configurable via `REFRESH_COOKIE_PATH` env var.
- Development: `REFRESH_COOKIE_PATH=/api/auth/refresh`
- Production: `REFRESH_COOKIE_PATH=/auth/refresh`

**Dependencies:** Step 2A.6
**Risk:** Medium — cookie path mismatch silently breaks auth refresh

---

## Phase 3: Recommendations & User Features (Outline)

Phase 3 is intentionally underspecified per SPEC.md. Structural outline only:

### 3.1 Backend: Recommendations Endpoint

- `GET /recommendations/{user_id}` — requires auth, user can only request own recommendations
- Integrates existing SVD recommender from `recommender/`
- Returns `list[Book]` with recommendation scores
- Fallback: popular books if user has no ratings

### 3.2 Frontend: Profile Page

- Route: `/profile` (protected)
- Sections: "My Rated Books" + "Recommended for You"
- Uses `GET /ratings/?user_id={id}` and `GET /recommendations/{user_id}`

### 3.3 Browse Page Enhancement

- "Recommended" section/tab for authenticated users

### 3.4 Open Questions

- Should recommender run as Dagster job or on-demand?
- Will pgvector semantic search replace ILIKE text search?
- Reading lists feature needs full design

---

## Dependency Graph

```
Phase 1 (can run in parallel):
  Step 1.1 (slugify + genre routes)
    └── Step 1.2 (fix MobileGenreSelect) [depends on 1.1]
  Step 1.3 (SearchBar sync) [independent]
  Step 1.4 (search 400 vs 422) [independent, optional]

Phase 2A - Backend (mostly sequential):
  Step 2A.1 (config) ──┐
  Step 2A.2 (deps) ────┤
  Step 2A.3 (models) ──┼── Step 2A.4 (auth module) ──┐
                        │                              │
  Step 2A.5 (limiter) ─┘                              │
                                                       ├── Step 2A.6 (main.py refactor)
  Step 2A.7 (compose) [depends on 2A.1]               │
  Step 2A.8 (Dockerfile) [depends on 2A.2]            │

Phase 2B - Frontend (partial parallelism):
  Step 2B.1 (types) ──────────────────┐
  Step 2B.11 (validation utils) ──┐   │
  Step 2B.6 (StarRating) ────┐   │   │
                              │   │   │
  Step 2B.2 (AuthContext) ────┼───┼───┘
    ├── Step 2B.3 (API client)│   │
    │     └── Step 2B.10 (connect auth to client)
    ├── Step 2B.4 (LoginPage) ┘   │
    ├── Step 2B.5 (RegisterPage) ─┘
    └── Step 2B.9 (App.tsx routes + header)
  Step 2B.7 (useRatings) ────┐
    └── Step 2B.8 (BookDetailPage rating)
  Step 2B.12 (cookie path fix) [depends on 2A.6]
```

---

## Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Cookie path mismatch in dev (Vite proxy rewrites URLs but cookie path doesn't match) | **High** | Make cookie path configurable via env var |
| 401 refresh queue race conditions | Medium | Use proven subscriber queue pattern, test thoroughly |
| `get_current_user` dependency injection with nested `Depends()` | Medium | Test the chain carefully |
| `SECRET_KEY` must be consistent across restarts | Medium | Generate once, store in `.env` |
| RefreshToken table needs creation | Low | `create_all()` is additive, won't drop existing tables |
| Hardcoded DB credentials in existing code | Low (dev) / High (prod) | Config module requires env vars for sensitive values |

---

## Recommended Execution Order

1. **Phase 1 fixes** (Steps 1.1-1.4) — small, self-contained PR
2. **Phase 2A backend** (Steps 2A.1-2A.8) — get auth working and tested
3. **Phase 2B frontend** (Steps 2B.1-2B.12) — build against working backend

---

## New Files Summary

| File | Purpose |
|------|---------|
| `frontend/src/utils/slugify.ts` | Genre slug conversion |
| `frontend/src/utils/validation.ts` | Form validation rules |
| `frontend/src/context/AuthContext.tsx` | Auth state management |
| `frontend/src/pages/LoginPage.tsx` | Login form |
| `frontend/src/pages/RegisterPage.tsx` | Registration form |
| `frontend/src/components/StarRating.tsx` | Interactive star rating |
| `frontend/src/hooks/useRatings.ts` | Ratings React Query hooks |
| `backend/app/config.py` | Centralized config |
| `backend/app/auth.py` | JWT logic + dependencies |
| `backend/app/rate_limit.py` | Rate limiter setup |

## Modified Files Summary

| File | Change |
|------|--------|
| `frontend/src/App.tsx` | AuthProvider, slug routes, login/register routes, header auth |
| `frontend/src/api/client.ts` | Auth header injection, 401 refresh interceptor |
| `frontend/src/pages/BrowsePage.tsx` | Parse slug param, resolve to genre ID |
| `frontend/src/pages/BookDetailPage.tsx` | Slug-based genre links, rating section |
| `frontend/src/components/GenreSidebar.tsx` | Slug-based links, fix MobileGenreSelect |
| `frontend/src/components/SearchBar.tsx` | useEffect for value sync |
| `frontend/src/types/index.ts` | Auth-related TypeScript interfaces |
| `backend/app/main.py` | CORS, JWT auth endpoints, rate limiting, protected ratings |
| `backend/db/models.py` | RefreshToken, UserCreate validators, RatingCreate, AuthResponse |
| `backend/requirements.txt` | python-jose, slowapi |
| `backend/Dockerfile` | Fix filename, Python 3.12 |
| `compose.yaml` | SECRET_KEY, CORS_ORIGINS env vars |

---

## Success Criteria

### Phase 1
- [ ] Genre URLs use slugs (`/genre/literary-fiction` not `/genre/3`)
- [ ] MobileGenreSelect uses React Router navigation (no full page reloads)
- [ ] SearchBar value syncs with URL state on browser navigation

### Phase 2
- [ ] Users can register with username/password validation
- [ ] Users can log in and receive JWT access token + httpOnly refresh cookie
- [ ] Access token is stored in memory only (not localStorage)
- [ ] Page refresh restores auth state via silent token refresh
- [ ] Authenticated users see interactive star rating on book detail pages
- [ ] Unauthenticated users see "Log in to rate" prompt (not hidden UI)
- [ ] Rating submission is optimistic with rollback on error
- [ ] Header shows login/register links or username/logout
- [ ] Protected `POST /ratings/` derives `user_id` from JWT
- [ ] Rate limiting enforced: login 5/min, register 3/min, ratings 30/min
- [ ] CORS allows `http://localhost:5173` with credentials
- [ ] Generic error messages prevent user enumeration
- [ ] 401 responses trigger automatic token refresh attempt

### Phase 3 (Deferred)
- [ ] Recommendation endpoint returns personalized results
- [ ] Profile page shows rated books and recommendations

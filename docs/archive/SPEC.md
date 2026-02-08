# SPEC.md — React Frontend for LitMatch

## Overview

Replace the Streamlit frontend with a React SPA for book discovery, browsing, and rating. The React app communicates with the existing FastAPI backend via REST API.

**Tech stack:** Vite + React + TypeScript + Tailwind CSS + React Router + TanStack React Query

**Design aesthetic:** Bookstore/literary — warm tones, serif fonts for titles, feels like a curated bookshop.

---

## Phases

### Phase 1 — Browse & Discover (MVP)

Book listing, genre filtering, search, book detail pages with critic reviews. No auth.

### Phase 2 — Auth & Ratings

JWT authentication (in-memory access token + httpOnly refresh cookie), user registration/login, book rating submission, viewing own ratings. Includes backend changes.

### Phase 3 — Recommendations & User Features

Personalized recommendations (integrate existing SVD recommender), user profile page, reading lists.

---

## Phase 1: Browse & Discover

### Pages & Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Home / Browse | Paginated book grid with genre filter sidebar |
| `/genre/:slug` | Genre Browse | Filtered view of browse page for a specific genre |
| `/books/:id` | Book Detail | Full book info, cover, description, critic reviews |

### Book Browse Page (`/` and `/genre/:slug`)

- **Book cards** display: cover image, title, author name, genre tags (max 3 shown alphabetically; if more than 3, show a `+N more` badge), average critic rating.
- **Traditional pagination** — page numbers with prev/next. 24 books per page (4x6 grid on desktop).
- **Genre sidebar** — list of all genres fetched from `GET /genres/`. Clicking a genre navigates to `/genre/:slug`. Active genre is highlighted.
- **Search bar** — top of page, queries backend on submit/enter. Searches by title and author.
- **Skeleton loading** — card-shaped placeholders with shimmer animation while data loads.
- **Empty state** — friendly message when no books match filters/search.
- On genre pages, the same browse layout is used but pre-filtered to that genre. The genre sidebar still shows all genres with the current one highlighted.

### Search Behavior

- **Endpoint:** `GET /books/search?q={query}&page={n}&limit={n}`
- **Empty query** (`q=` or `q` omitted): return 400 with `{ "detail": "Search query must not be empty" }`. Frontend disables submit when input is blank.
- **Minimum query length:** 2 characters. Shorter queries return 400.
- **Search fields:** Title and author name. Case-insensitive partial matching (SQL `ILIKE '%query%'`). Future phases may replace with pgvector semantic search.
- **Result ranking:** Exact title matches first, then title-contains, then author-contains. Within each tier, alphabetical by title.
- **No results:** Return `{ items: [], total: 0, page: 1, limit: 24 }`. Frontend shows "No books found for '{query}'" with a "Clear search" button.
- **Invalid page/limit:** Non-integer or negative values return 422. `limit` clamped to 1-100.

### Pagination Behavior

- Page numbering starts at 1. Default `page=1`, `limit=24`, max `limit=100`.
- **Page exceeds total:** Backend returns `{ items: [], total: N, page: requested_page, limit: 24 }`. Frontend detects `items.length === 0 && total > 0` and redirects to page 1.
- **Page 0 or negative:** 422 validation error.
- **Fewer results than limit:** Normal behavior for the last page.

### Null Field Fallback Behavior

Book data may have null fields. Frontend handles each case:

| Field | Fallback |
|-------|----------|
| `cover` | Placeholder SVG (muted book icon on warm-toned background) |
| `author` | "Unknown Author" in italics |
| `publisher` | Omit the publisher line entirely |
| `publish_date` | Omit the date line entirely |
| `description` | "No description available." in muted text |
| `genres` | Show nothing in the genre tag area |

### Empty States

Three distinct empty states with different messages:

1. **No books at all** (database empty, no filters active): "No books available yet. Check back soon!"
2. **No search results**: "No books found for '{query}'." with a "Clear search" button.
3. **No books in genre**: "No books in {genre} yet." with a "Browse all books" link.

### Book Detail Page (`/books/:id`)

- Cover image (large), title (serif font), author, publisher, publish date, description.
- Genre tags as clickable links (navigate to `/genre/:slug`).
- **Critic reviews section** — list of reviews showing: critic name (or "Anonymous"), publication name (or omit), rating badge (Rave/Positive/Mixed/Pan with color coding), review excerpt. Fetched from `GET /reviews/{book_id}`. Show first 5 reviews; if more exist, display a "Show all N reviews" button to expand.
- The `url` field on Book is the source URL from bookmarks.reviews (not displayed to the user).
- Back button / breadcrumb to return to browse.

### State Management (Phase 1)

- **TanStack React Query** for all server state: book lists, genres, book details, reviews.
  - Stale time: 5 minutes for book lists, 10 minutes for genres (rarely change).
  - Query keys: `['books', { page, genre, search }]`, `['book', id]`, `['reviews', bookId]`, `['genres']`.
- No global state needed in Phase 1.

### Error Handling

- **Error boundaries** wrapping each page — show a "Something went wrong" message with retry button.
- **Toast notifications** (lightweight, e.g. `react-hot-toast`) for non-critical errors like a single API call failing.
- If the backend is unreachable, the error boundary catches it with a "Cannot connect to server" message.

---

## Phase 2: Auth & Ratings

### New Pages & Routes

| Route | Page | Description |
|-------|------|-------------|
| `/login` | Login | Username + password form |
| `/register` | Register | Username + password + confirm password form |

### JWT Authentication Flow

**Token strategy: in-memory access token + httpOnly refresh token cookie.**

1. User logs in via `POST /auth/login` → backend returns access token in response body and sets httpOnly refresh cookie.
2. Access token stored in memory (React ref/variable, NOT localStorage). Lost on page refresh by design.
3. On page load / token expiry, call `POST /auth/refresh` → backend validates refresh cookie, returns new access token.
4. Access token sent as `Authorization: Bearer <token>` header on authenticated requests.
5. Logout calls `POST /auth/logout` → backend clears the refresh cookie.

**Protected routes:** Rating submission requires auth. Browsing does not. Use a React Context (`AuthContext`) to track auth state and provide `user`, `login()`, `logout()`, `isAuthenticated`.

**UX:** If an unauthenticated user tries to rate a book, show a prompt to log in (link to `/login`) rather than hiding the rating UI entirely.

### Rating UI (Book Detail Page)

- Star rating component (1-5 stars) below the critic reviews section.
- If authenticated: show interactive stars, current user rating if one exists, and a "Rate" button.
- Optimistic update — show the new rating immediately, roll back on error with a toast.
- Calls `POST /ratings/` to create/update rating.

### Rating Scale

- **Critic reviews:** Integer 1-4 mapped from qualitative ratings (1=Pan, 2=Mixed, 3=Positive, 4=Rave). Displayed as colored badges (red/amber/blue/green), **not** stars.
- **User ratings:** Integer 1-5. Whole stars only — no half-stars, no floats. Backend validates `1 <= rating <= 5` and rejects out-of-range values with 422.

### Backend Changes Required (Phase 2)

#### JWT Auth Endpoints

Replace the current basic auth with JWT-based auth:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/login` | Validate credentials, return access token + set httpOnly refresh cookie |
| `POST` | `/auth/register` | Create user, return access token + set httpOnly refresh cookie |
| `POST` | `/auth/refresh` | Validate refresh cookie, return new access token |
| `POST` | `/auth/logout` | Clear refresh cookie |

- Access tokens: short-lived (15 min), contain `user_id` and `username` in payload.
- Refresh tokens: longer-lived (7 days), stored as httpOnly, Secure, SameSite=Strict cookie. Path set to `/auth/refresh` to limit cookie scope.
- Use `python-jose` for JWT encoding/decoding.
- Add a `Depends(get_current_user)` dependency for protected endpoints (`POST /ratings/`).

#### Registration & Login Error Messages

To prevent user enumeration:
- `POST /auth/register` with an existing username: return 400 with `{ "detail": "Registration failed" }` (NOT "Username already exists").
- `POST /auth/login` with wrong credentials: return 401 with `{ "detail": "Invalid credentials" }` (generic, no hint about which field is wrong).

#### Input Validation

- **Username:** 3-30 characters, alphanumeric plus underscores only (`^[a-zA-Z0-9_]{3,30}$`). Reject with 422 if invalid.
- **Password:** Minimum 8 characters. Must contain at least one letter and one digit. Reject with 422 if invalid.

#### Rate Limiting

Apply rate limiting (e.g., `slowapi`):
- `POST /auth/login`: 5 attempts per minute per IP.
- `POST /auth/register`: 3 attempts per minute per IP.
- `POST /ratings/`: 30 per minute per user.
- Return 429 with `{ "detail": "Rate limit exceeded. Try again in {N} seconds." }` and `Retry-After` header.

#### CORS Middleware

Add to `backend/app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev; configurable via CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
```

Production `allow_origins` must be set via `CORS_ORIGINS` environment variable (comma-separated). Never use `["*"]` with `allow_credentials=True`.

---

## Phase 3: Recommendations & User Features

### New Pages & Routes

| Route | Page | Description |
|-------|------|-------------|
| `/profile` | User Profile | User's rated books and personalized recommendations |

### Recommendations

- New endpoint: `GET /recommendations/{user_id}` — returns recommended books from the SVD recommender.
- Profile page shows: list of books the user has rated, and a "Recommended for You" section.
- Browse page gets a "Recommended" tab/section for authenticated users.

### Scope Note

Phase 3 is intentionally underspecified. Exact features and UX will be defined based on learnings from Phases 1 and 2.

---

## Existing API Endpoints

These endpoints already exist in the FastAPI backend (`backend/app/main.py`):

| Method | Endpoint | Response | Notes |
|--------|----------|----------|-------|
| `GET` | `/books/?offset={n}&limit={n}&genre={id}` | `Book[]` | Returns books; limit max 100. Uses `offset` not `page`. No total count. |
| `GET` | `/books/{book_id}` | `Book` | Single book with author, publisher, genres, reviews. 404 if not found. |
| `GET` | `/reviews/{book_id}` | `Review[]` | All reviews for a book. Currently returns 404 if none exist (should return `[]`). |
| `GET` | `/genres/` | `Genre[]` | All genres. |
| `GET` | `/ratings/?user_id={n}&book_id={n}` | `UserRating[]` | Filter by user and/or book. |
| `POST` | `/ratings/` | `UserRating` | Create or update a rating. **No auth required currently.** |
| `POST` | `/auth/register` | `UserPublic` | Create user. Returns `{id, username}`. No JWT yet. |
| `POST` | `/auth/login` | `UserPublic` | Validate credentials. Returns `{id, username}`. No JWT yet. |

---

## API Changes Required for React Frontend

| Phase | Method | Endpoint | Change |
|-------|--------|----------|--------|
| 1 | `GET` | `/books/?page={n}&limit={n}&genre={id}` | **Modify**: change `offset` to `page`-based. Return `{ items: Book[], total: N, page: N, limit: N }`. |
| 1 | `GET` | `/books/search?q={query}&page={n}&limit={n}` | **New**: full-text search by title/author. Same paginated response shape. |
| 1 | `GET` | `/reviews/{book_id}` | **Modify**: return empty `[]` instead of 404 when no reviews exist. |
| 2 | `POST` | `/auth/login` | **Modify**: return JWT access token + set httpOnly refresh cookie. |
| 2 | `POST` | `/auth/register` | **Modify**: return JWT access token + set httpOnly refresh cookie. |
| 2 | `POST` | `/auth/refresh` | **New**: validate refresh cookie, issue new access token. |
| 2 | `POST` | `/auth/logout` | **New**: clear refresh cookie. |
| 2 | `POST` | `/ratings/` | **Modify**: require `Depends(get_current_user)`. Derive `user_id` from JWT, not request body. Request body: `{ book_id: int, rating: int }`. |
| 3 | `GET` | `/recommendations/{user_id}` | **New**: personalized recommendations from SVD recommender. |

---

## API Error Response Format

All backend error responses use the standard FastAPI shape:

```json
{ "detail": "Human-readable error message" }
```

Validation errors (422) return an array:

```json
{ "detail": [{ "loc": ["query", "page"], "msg": "value is not a valid integer", "type": "type_error.integer" }] }
```

**Frontend error handling rules:**
1. `detail` is a string → display it directly in a toast.
2. `detail` is an array (validation error) → display "Invalid request. Please check your input."
3. Network error (no response) → display "Cannot connect to server. Please try again."
4. 500 error → display "Something went wrong. Please try again later." (never show raw server text).

---

## Project Structure

```
frontend/               # Replaces existing Streamlit app
├── index.html
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── vite.config.ts
├── public/
└── src/
    ├── main.tsx                 # App entry point
    ├── App.tsx                  # Router setup, QueryClient provider
    ├── api/
    │   └── client.ts            # Axios/fetch wrapper, auth header injection, base URL config
    ├── hooks/
    │   ├── useBooks.ts          # React Query hooks for books (list, detail, search)
    │   ├── useGenres.ts         # React Query hook for genres
    │   ├── useReviews.ts        # React Query hook for reviews
    │   └── useRatings.ts        # React Query hook for ratings (Phase 2)
    ├── context/
    │   └── AuthContext.tsx       # Auth state, login/logout/refresh logic (Phase 2)
    ├── pages/
    │   ├── BrowsePage.tsx       # Book grid + genre sidebar + search + pagination
    │   ├── BookDetailPage.tsx   # Book info + reviews + rating
    │   ├── LoginPage.tsx        # (Phase 2)
    │   └── RegisterPage.tsx     # (Phase 2)
    ├── components/
    │   ├── BookCard.tsx         # Cover, title, author, genres, rating
    │   ├── BookGrid.tsx         # Grid layout of BookCards
    │   ├── GenreSidebar.tsx     # Genre filter list
    │   ├── SearchBar.tsx        # Search input
    │   ├── Pagination.tsx       # Page number navigation
    │   ├── ReviewList.tsx       # List of critic reviews
    │   ├── StarRating.tsx       # Interactive star rating (Phase 2)
    │   ├── Skeleton.tsx         # Skeleton loading placeholders
    │   └── ErrorBoundary.tsx    # Error boundary wrapper
    └── types/
        └── index.ts             # TypeScript interfaces matching backend models
```

---

## Responsive Behavior

Desktop-first, mobile-friendly:

- **Desktop (1024px+):** 4-column book grid, genre sidebar visible on left.
- **Tablet (768-1023px):** 3-column grid, genre sidebar collapses to a horizontal scrollable chip bar above the grid.
- **Mobile (<768px):** 2-column grid, genre filter as a dropdown select above the grid, search bar full-width.

---

## Key TypeScript Types

Derived from `backend/db/models.py`:

```typescript
interface Book {
  id: number;
  title: string;
  author_id: number | null;
  publisher_id: number | null;
  publish_date: string | null;  // ISO date
  description: string;
  url: string;
  cover: string | null;
  author: Author | null;
  publisher: Publisher | null;
  genres: Genre[];
}

interface Author {
  id: number;
  name: string;
}

interface Publisher {
  id: number;
  name: string;
}

interface Genre {
  id: number;
  name: string;
}

interface Review {
  id: number;
  book_id: number;
  rating: number;
  review: string;
  url: string;
  critic: Critic | null;
  publication: Publication | null;
}

interface Critic {
  id: number;
  name: string;
}

interface Publication {
  id: number;
  name: string;
}

interface UserRating {
  id: number;
  user_id: number;
  book_id: number;
  rating: number;
  created_at: string;
  updated_at: string;
}

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}
```

---

## Dependencies

```json
{
  "dependencies": {
    "react": "^19",
    "react-dom": "^19",
    "react-router": "^7",
    "@tanstack/react-query": "^5",
    "axios": "^1",
    "react-hot-toast": "^2"
  },
  "devDependencies": {
    "typescript": "^5",
    "vite": "^6",
    "tailwindcss": "^4",
    "@types/react": "^19",
    "@types/react-dom": "^19"
  }
}
```

---

## Security Hardening (Pre-Production)

Not required for development, but must be addressed before any production deployment:

- **Security headers middleware:** Add `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `Referrer-Policy: strict-origin-when-cross-origin`.
- **Error response sanitization:** Ensure `debug=False` in production. Global exception handler returns generic 500 responses; full tracebacks logged server-side only.
- **Credentials management:** `.env` must be in `.gitignore`. Remove hardcoded credential defaults from source. Require `DATABASE_URL` and `SECRET_KEY` environment variables to be set.

---

## Open Questions for Future Phases

- Should book detail pages be SSR-friendly for SEO (would require migrating to Next.js or Remix)?
- Should the recommender run as a background Dagster job or be computed on-demand per request?
- Will pgvector-based semantic search replace or augment the text search endpoint?
- The ETL pipeline computes an `is_fiction` flag via genre classification, but it is not persisted to the database (`Book` model lacks this column). Fiction/non-fiction distinction is currently handled via genre filter. Add a dedicated flag if explicit filtering is desired.

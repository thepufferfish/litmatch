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

- **Book cards** display: cover image, title, author name, genre tags (max 3), average critic rating.
- **Traditional pagination** — page numbers with prev/next. 24 books per page (4x6 grid on desktop).
- **Genre sidebar** — list of all genres fetched from `GET /genres/`. Clicking a genre navigates to `/genre/:slug`. Active genre is highlighted.
- **Search bar** — top of page, queries backend on submit/enter. Searches by title and author.
- **Skeleton loading** — card-shaped placeholders with shimmer animation while data loads.
- **Empty state** — friendly message when no books match filters/search.
- On genre pages, the same browse layout is used but pre-filtered to that genre. The genre sidebar still shows all genres with the current one highlighted.

### Book Detail Page (`/books/:id`)

- Cover image (large), title (serif font), author, publisher, publish date, description.
- Genre tags as clickable links (navigate to `/genre/:slug`).
- **Critic reviews section** — list of reviews showing: critic name, publication, rating, review excerpt. Fetched from `GET /reviews/{book_id}`.
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
- Refresh tokens: longer-lived (7 days), stored as httpOnly, Secure, SameSite=Lax cookie.
- Use `python-jose` for JWT encoding/decoding.
- Add a `Depends(get_current_user)` dependency for protected endpoints (`POST /ratings/`).

#### CORS Middleware

Add to `backend/app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,  # Required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Production origins should be configurable via environment variable.

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

## New API Endpoints Needed

These endpoints don't exist yet and are required for the React frontend:

| Phase | Method | Endpoint | Purpose |
|-------|--------|----------|---------|
| 1 | `GET` | `/books/search?q={query}&page={n}&limit={n}` | Search books by title/author. Returns paginated results with total count. |
| 1 | `GET` | `/books/?page={n}&limit={n}&genre={id}` | **Modify existing** — add `total_count` to response for pagination (return `{ books: [...], total: N }`). |
| 2 | `POST` | `/auth/login` | **Modify existing** — return JWT access token + set refresh cookie. |
| 2 | `POST` | `/auth/register` | **Modify existing** — return JWT access token + set refresh cookie. |
| 2 | `POST` | `/auth/refresh` | Validate refresh cookie, issue new access token. |
| 2 | `POST` | `/auth/logout` | Clear refresh cookie. |
| 3 | `GET` | `/recommendations/{user_id}` | Get personalized book recommendations. |

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
- **Tablet (768-1023px):** 3-column grid, sidebar collapses to horizontal filter bar or hamburger.
- **Mobile (<768px):** 2-column grid, genre filter as dropdown/modal, search bar full-width.

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

## Open Questions for Future Phases

- Should book detail pages be SSR-friendly for SEO (would require migrating to Next.js or Remix)?
- Should the recommender run as a background Dagster job or be computed on-demand per request?
- Will pgvector-based semantic search replace or augment the text search endpoint?

# Frontend Codemap

> Freshness: 2026-02-08 | Auto-generated from source analysis

## Module Graph

```
main.tsx → App.tsx
             ├── QueryClientProvider
             ├── BrowserRouter
             ├── AuthProvider (context/AuthContext)
             │    └── api/client.ts (axios)
             ├── ErrorBoundary
             └── Routes
                  ├── BrowsePage ──→ useBooks, useGenres, GenreSidebar, SearchBar, BookGrid, Pagination
                  ├── BookDetailPage ──→ useBook, useReviews, useRatings, ReviewList, StarRating
                  ├── LoginPage ──→ useAuth, validation utils
                  └── RegisterPage ──→ useAuth, validation utils
```

## Routes

| Path | Component | Data Hooks |
|------|-----------|------------|
| `/` | BrowsePage | useBooks, useGenres |
| `/genre/:slug` | BrowsePage | useBooks, useGenres |
| `/books/:id` | BookDetailPage | useBook, useReviews, useUserRating |
| `/login` | LoginPage | useAuth (context) |
| `/register` | RegisterPage | useAuth (context) |
| `*` | NotFoundPage | — |

## API Client (`src/api/client.ts`)

- Base: `/api` (Vite proxies to `http://localhost:8000`, strips `/api` prefix)
- Request interceptor: injects `Authorization: Bearer {token}`
- Response interceptor: auto-refresh on 401, error toasts on 429/500
- `setAuthHelpers(getter, setter)` — registered by AuthContext on mount

## Auth Context (`src/context/AuthContext.tsx`)

- Token stored in React ref (not localStorage)
- `login()`, `register()`, `logout()` — API calls + state updates
- Silent refresh on mount via POST `/auth/refresh`
- Provides `user`, `isLoading`, `getAccessToken()`

## Hooks (TanStack React Query v5)

| Hook | Query Key | Endpoint | Stale Time |
|------|-----------|----------|------------|
| `useBooks` | `["books", {page, limit, genre}]` | GET /books/ | 5 min |
| `useBook` | `["book", id]` | GET /books/:id | default |
| `useSearchBooks` | `["books", {search, page, limit}]` | GET /books/search | default |
| `useGenres` | `["genres"]` | GET /genres/ | 10 min |
| `useReviews` | `["reviews", bookId]` | GET /reviews/:id | 5 min |
| `useUserRating` | `["rating", {bookId, userId}]` | GET /ratings/ | default |
| `useSubmitRating` | mutation | POST /ratings/ | — |

## Components

| Component | Props | Purpose |
|-----------|-------|---------|
| BookCard | `{book}` | Thumbnail with cover, title, author, genre tags |
| BookGrid | `{books, isLoading}` | Responsive grid (2/3/4 cols) |
| GenreSidebar | `{activeGenreSlug?}` | Desktop sidebar / tablet chips / mobile dropdown |
| SearchBar | `{initialValue?, onSearch, onClear}` | Search input with 2-char minimum |
| Pagination | `{currentPage, totalPages, onPageChange}` | Page nav with ellipsis |
| ReviewList | `{reviews}` | Critic reviews with rating badges, expandable |
| StarRating | `{value, onChange?, disabled?}` | Interactive 5-star widget |
| Skeleton | — | SkeletonGrid + SkeletonDetail shimmer placeholders |
| ErrorBoundary | `{children, fallback?}` | React error boundary with retry |

## Utils

| Function | File | Purpose |
|----------|------|---------|
| `slugify(name)` | slugify.ts | Genre name → URL slug |
| `validateUsername(v)` | validation.ts | 3-30 chars, alphanumeric + underscore |
| `validatePassword(v)` | validation.ts | 8-72 chars, letter + digit required |

## Dependency Stack

```
React 19 + ReactDOM 19
├── @tanstack/react-query v5 (data fetching)
├── react-router v7 (routing)
├── axios v1 (HTTP client)
├── react-hot-toast v2 (notifications)
├── Tailwind CSS v4 (styling)
├── Vite v6 (bundler)
├── TypeScript v5 (strict mode)
└── Vitest v4 + Testing Library (tests)
```

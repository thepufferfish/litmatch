# Frontend Codemap

> Freshness: 2026-02-15 | Auto-generated from source analysis

## Module Graph

```
main.tsx -> App.tsx
             +-- QueryClientProvider
             +-- BrowserRouter
             +-- AuthProvider (context/AuthContext)
             |    +-- api/client.ts (axios)
             +-- ErrorBoundary
             +-- Routes
                  +-- BrowsePage ----> useBooks, useSearchBooks, useGenres, useUserRatingsMap
                  |                    GenreSidebar, SubgenreFilter, SearchBar, SortSelect
                  |                    BookGrid, Pagination, useSubmitRating, useDeleteRating
                  +-- BookDetailPage -> useBook, useReviews, useRatings, ReviewList, InlineRating
                  +-- ProfilePage ----> useRecommendations, useGroupedGenres, useUserProfile
                  |                     RecommendationGrid, SubgenreFilter
                  +-- MyRatingsPage --> useUserRatedBooks, BookGrid, Pagination, SortSelect
                  +-- LoginPage ------> useAuth, validation utils
                  +-- RegisterPage --> useAuth, validation utils
```

## Routes

| Path | Component | Data Hooks |
|------|-----------|------------|
| `/` | BrowsePage | useBooks, useSearchBooks, useGenres, useUserRatingsMap |
| `/genre/:slug` | BrowsePage | useBooks, useGenres, useUserRatingsMap |
| `/books/:id` | BookDetailPage | useBook, useReviews, useRatings |
| `/login` | LoginPage | useAuth (context) |
| `/register` | RegisterPage | useAuth (context) |
| `/profile` | ProfilePage | useRecommendations, useGroupedGenres, useUserProfile |
| `/ratings` | MyRatingsPage | useUserRatedBooks |
| `*` | NotFoundPage | -- |

## API Client (`src/api/client.ts`)

- Base: `/api` (Vite proxies to `http://localhost:8000`, strips `/api` prefix)
- Request interceptor: injects `Authorization: Bearer {token}`
- Response interceptor: auto-refresh on 401 (shared promise), error toasts on 429/500
- `setAuthHelpers(getter, setter)` -- registered by AuthContext on mount

## Auth Context (`src/context/AuthContext.tsx`)

- Token stored in React ref (not localStorage)
- `login()`, `register()`, `logout()` -- API calls + state updates
- Silent refresh on mount via POST `/auth/refresh`
- Provides `user`, `isLoading`, `getAccessToken()`

## Hooks (TanStack React Query v5)

| Hook | Query Key | Endpoint | Notes |
|------|-----------|----------|-------|
| `useBooks` | `["books", {page, limit, genre, sort, category}]` | GET /books/ | 5 min stale, NaN/Infinity guard |
| `useBook` | `["book", id]` | GET /books/:id | -- |
| `useSearchBooks` | `["books", {search, page, limit}]` | GET /books/search | -- |
| `useGenres` | `["genres"]` | GET /genres/ | 10 min stale |
| `useGroupedGenres` | `["genres", "grouped"]` | GET /genres/grouped | Fiction/nonfiction/unknown |
| `useReviews` | `["reviews", bookId]` | GET /reviews/:id | 5 min stale |
| `useUserRatings` | `["ratings"]` | GET /ratings/ | Auth required |
| `useUserRatingsMap` | `["ratings"]` | GET /ratings/ | Returns Map<bookId, rating> |
| `useSubmitRating` | mutation | POST /ratings/ | Optimistic update |
| `useDeleteRating` | mutation | DELETE /ratings/:id | Optimistic update |
| `useRecommendations` | `["recommendations", {...}]` | GET /recommendations/ | Category + genre filters |
| `useUserProfile` | `["user", "profile"]` | GET /users/me | Username + rating count |
| `useUserRatedBooks` | `["rated-books", {page, sort}]` | GET /users/me/rated-books/ | Paginated |

## Components

| Component | Props | Purpose |
|-----------|-------|---------|
| BookCard | `{book, userRating?, onRate?, onDelete?}` | Cover, title, author, genres, critic badge, inline rating |
| BookGrid | `{books, isLoading, ...rating}` | Responsive grid (2/3/4 cols) with skeleton loaders |
| GenreSidebar | `{activeGenreSlug?, category?}` | Desktop sidebar / tablet chips / mobile dropdown with fiction/nonfiction tabs |
| SubgenreFilter | `{genres, selected, onSelect}` | Dropdown for filtering subgenres within fiction/nonfiction |
| SearchBar | `{initialValue?, onSearch, onClear}` | Debounced search input with clear button |
| SortSelect | `{value, onChange}` | Sort dropdown (title, date, rating, reviews) |
| Pagination | `{currentPage, totalPages, onPageChange}` | First/prev/next/last with ellipsis |
| StarRating | `{value, onChange?, disabled?}` | Interactive 5-star widget |
| InlineRating | `{bookId, rating?, onRate?, onDelete?}` | Inline star rating with loading state |
| CriticRatingBadge | `{avgRating, reviewCount}` | Badge showing avg critic rating + count |
| ReviewList | `{reviews}` | Critic reviews with rating badges, expandable |
| RecommendationGrid | `{books, strategy}` | Recommendation grid with personalized/popular badge |
| Skeleton | -- | SkeletonGrid + SkeletonDetail shimmer placeholders |
| ErrorBoundary | `{children, fallback?}` | React error boundary with retry |

## Utils

| Function | File | Purpose |
|----------|------|---------|
| `slugify(name)` | slugify.ts | Genre name -> URL slug |
| `validateUsername(v)` | validation.ts | 3-30 chars, alphanumeric + underscore |
| `validatePassword(v)` | validation.ts | 8-72 chars, letter + digit required |

## Dependency Stack

```
React 19 + ReactDOM 19
+-- @tanstack/react-query v5 (data fetching)
+-- react-router v7 (routing)
+-- axios v1 (HTTP client)
+-- react-hot-toast v2 (notifications)
+-- Tailwind CSS v4 (styling)
+-- Vite v6 (bundler)
+-- TypeScript v5 (strict mode)
+-- Vitest v4 + Testing Library (tests)
```

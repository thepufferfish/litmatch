# Frontend Roadmap

**Tech Stack:** Vite + React 19 + TypeScript + Tailwind CSS 4 + React Router 7 + TanStack React Query 5

**Archived Spec:** [archive/SPEC.md](archive/SPEC.md)

## Phase 1: Browse & Discover — DONE

All items implemented and verified.

### Features
- BrowsePage with paginated 4x6 book grid (responsive: 3-col tablet, 2-col mobile)
- Genre sidebar (desktop list, tablet chips, mobile dropdown) with slug-based routes
- SearchBar with URL state sync, min 2 chars, clear button
- BookDetailPage with cover, metadata, description, genre tag links, critic reviews
- BookCard with cover fallback, author, genre tags (max 3 + "+N more"), rating badge
- Pagination with page numbers, prev/next
- Skeleton loading (card placeholders + detail page skeleton)
- ErrorBoundary with retry
- Toast notifications (react-hot-toast)
- Three distinct empty states (no books, no search results, no books in genre)
- Null field fallbacks for all 6 nullable Book fields
- TanStack React Query with stale times (5 min books, 10 min genres)

### Key Files
- Pages: `BrowsePage.tsx`, `BookDetailPage.tsx`
- Components: `BookCard.tsx`, `BookGrid.tsx`, `GenreSidebar.tsx`, `SearchBar.tsx`, `Pagination.tsx`, `ReviewList.tsx`, `Skeleton.tsx`, `ErrorBoundary.tsx`
- Hooks: `useBooks.ts`, `useGenres.ts`, `useReviews.ts`
- Utils: `slugify.ts`

## Phase 2: Auth & Ratings — DONE

All items implemented and verified.

### Features
- AuthContext with in-memory access token (useRef, not localStorage)
- Silent refresh on mount via `POST /auth/refresh`
- API client with auth header injection and 401 refresh queue pattern
- LoginPage with client-side validation, redirect if authenticated
- RegisterPage with confirm password, matching validation rules
- StarRating component (interactive + read-only, 1-5 stars, hover preview)
- Rating section in BookDetailPage (auth-aware: interactive if logged in, "Log in to rate" if not)
- Auth-aware header (login/signup links or username + logout)
- Form validation (username: 3-30 chars alphanumeric+underscore, password: 8+ with letter+digit)
- 404 NotFoundPage
- Rate limit error handling (429 toast)

### Key Files
- Context: `AuthContext.tsx`
- API: `client.ts` (auth interceptor)
- Pages: `LoginPage.tsx`, `RegisterPage.tsx`
- Components: `StarRating.tsx`
- Hooks: `useRatings.ts`
- Utils: `validation.ts`

## Phase 2.5: Browse Enhancements — DONE

Additions to the browse and detail experience implemented after Phase 2.

### Features
- SortSelect component with 6 sort options (Highest Rated, Most Reviewed, Newest/Oldest, Title A-Z/Z-A)
- Sort state persisted in URL parameters across page navigation and search
- CriticRatingBadge component with semantic labels (Rave/Positive/Mixed/Pan) and color-coded badges
- Average critic rating and review count displayed on both BookCard and BookDetailPage
- ReviewList component on detail page: critic name, publication, individual rating, review excerpt (4-line clamp), "Read full review" link with URL validation
- Expand/collapse for reviews (show first 5, "Show all N reviews" button)

### Key Files
- Components: `SortSelect.tsx`, `CriticRatingBadge.tsx`, `ReviewList.tsx` (enhanced)
- Updated: `BrowsePage.tsx`, `BookCard.tsx`, `BookDetailPage.tsx`

## Phase 3: Recommendations & Profile — PLANNED

**Depends on:** Backend Phase 3 (`GET /recommendations/`, `GET /users/me`)

**Reference:** [Recommender Roadmap](ROADMAP-RECOMMENDER.md) Phase 4

### 3.1 Profile Page
- **Route:** `/profile` (protected — redirect to /login if unauthenticated)
- **Sections:**
  - "My Rated Books" — grid of books the user has rated, with their star rating shown
  - "Recommended for You" — recommendations separated into Fiction and Non-Fiction tabs
- **Data:** `GET /ratings/` (scoped to current user), `GET /recommendations/` (auth required)
- **Strategy display:** Shows "Personalized" or "Popular" label based on `meta.strategy`
- **Empty states:**
  - No ratings: "You haven't rated any books yet"
  - < 5 ratings: "Rate N more books to get personalized recommendations" (shows popular books as fallback)
  - >= 5 ratings: Personalized recommendations with fiction/nonfiction tabs
- **New hook:** `useRecommendations(limit)`

### 3.2 Navigation
- Add "Recommended" link in authenticated header (links to `/profile`)
- Add `/profile` route (protected) to `App.tsx`

### 3.3 Recommendation Hook
- **File:** `src/hooks/useRecommendations.ts`
- Uses TanStack React Query with 5-minute stale time
- Calls `GET /recommendations/` with auth header
- Returns `RecommendationResponse` with `fiction`, `nonfiction`, and `meta` fields

### Estimated New Files
- `src/pages/ProfilePage.tsx`
- `src/hooks/useRecommendations.ts`
- Update `App.tsx` (add `/profile` route, protect it)
- Update `Header.tsx` (add "Recommended" link when authenticated)

### Open Questions
- Should profile show rating history with timestamps?
- Should there be a "delete rating" option?

## Phase 4: Semantic Search UI — PLANNED

**Depends on:** Backend Phase 4 (`GET /books/semantic-search`)

**Reference:** [Recommender Roadmap](ROADMAP-RECOMMENDER.md) Phase 5

### 4.1 Semantic Search Toggle
- Update `SearchBar.tsx` to offer a semantic search toggle (switch between ILIKE text search and embedding-based semantic search)
- Semantic search calls `GET /books/semantic-search?q={query}` instead of `GET /books/search?q={query}`
- Same `PaginatedResponse[BookRead]` shape — existing book grid works unchanged

### Future Considerations (Unplanned)
- Reading lists (requires backend design)
- Browse page "Recommended" section for authenticated users

## Future Considerations

- SSR migration (Next.js/Remix) for SEO on book detail pages
- Dark mode
- Social features (sharing, following)
- Admin dashboard
- Internationalization (i18n)
- User text reviews (in addition to star ratings)
- E2E tests with Playwright for critical flows

## Testing Status

| Test | Coverage | Status |
|------|----------|--------|
| `SearchBar.test.tsx` | SearchBar component | DONE |
| `StarRating.test.tsx` | StarRating component | DONE |
| `CriticRatingBadge.test.tsx` | CriticRatingBadge component | DONE |
| `ReviewList.test.tsx` | ReviewList component | DONE |
| `BookCard.test.tsx` | BookCard component | DONE |
| `BookGrid.test.tsx` | BookGrid component | DONE |
| `SortSelect.test.tsx` | SortSelect component | DONE |
| `GenreSidebar.test.tsx` | GenreSidebar component | DONE |
| `Pagination.test.tsx` | Pagination component | DONE |
| `ErrorBoundary.test.tsx` | ErrorBoundary component | DONE |
| `AuthContext.test.tsx` | Auth context (login/logout/register) | DONE |
| `BookDetailPage.test.tsx` | BookDetailPage (with auth/rating) | DONE |
| `BrowsePage.test.tsx` | BrowsePage unit tests | DONE |
| `BrowsePage.integration.test.tsx` | BrowsePage integration tests | DONE |
| `useBooks.test.ts` | Books hook | DONE |
| `useSearchBooks.test.ts` | Search hook | DONE |
| `useReviews.test.ts` | Reviews hook | DONE |
| `useRatings.test.ts` | Rating hooks | DONE |
| `client.test.ts` | API client | DONE |
| `slugify.test.ts` | Slug utility | DONE |
| `validation.test.ts` | Form validation | DONE |
| E2E tests (Playwright) | Critical user flows | NOT STARTED |

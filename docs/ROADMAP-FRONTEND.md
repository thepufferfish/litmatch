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

## Phase 3: Recommendations & User Features — PLANNED

**Depends on:** Backend Phase 3 (`GET /recommendations/{user_id}`)

### 3.1 Profile Page
- **Route:** `/profile` (protected — redirect to /login if unauthenticated)
- **Sections:**
  - "My Rated Books" — grid of books the user has rated, with their star rating shown
  - "Recommended for You" — grid of recommended books from the backend
- **Data:** `GET /ratings/` (scoped to current user), `GET /recommendations/{user_id}`
- **Empty states:** "You haven't rated any books yet" / "Rate more books to get recommendations"
- **New hook:** `useRecommendations(userId)`

### 3.2 Browse Page Enhancement
- Add "Recommended" tab or section visible only to authenticated users
- Show top N recommendations inline on browse page

### 3.3 Reading Lists (Underspecified)
- Allow users to create named lists and add books
- Requires backend endpoints: `POST /lists/`, `POST /lists/{id}/books/`, `GET /lists/`
- Needs full design before implementation

### Estimated New Files
- `src/pages/ProfilePage.tsx`
- `src/hooks/useRecommendations.ts`
- Update `App.tsx` (add `/profile` route, protect it)

### Open Questions
- Should profile show rating history with timestamps?
- Should there be a "delete rating" option?
- How many recommendations on browse page vs. profile page?
- Should reading lists be public or private?

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
| `BookDetailPage.test.tsx` | BookDetailPage (with auth/rating) | DONE |
| `useRatings.test.ts` | Rating hooks | DONE |
| `slugify.test.ts` | Slug utility | DONE |
| `validation.test.ts` | Form validation | DONE |
| E2E tests (Playwright) | Critical user flows | NOT STARTED |

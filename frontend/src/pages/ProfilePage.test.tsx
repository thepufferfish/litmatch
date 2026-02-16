import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProfilePage } from "./ProfilePage";
import type { Book, PaginatedRecommendationResponse, UserProfile } from "@/types";

// -- Mocks -------------------------------------------------------------------

const mockUseAuth = vi.fn();
const mockUseUserProfile = vi.fn();
const mockUseInfiniteRecommendations = vi.fn();
const mockUseGroupedGenres = vi.fn();

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("@/hooks/useUserProfile", () => ({
  useUserProfile: (...args: unknown[]) => mockUseUserProfile(...args),
}));

vi.mock("@/hooks/useInfiniteRecommendations", () => ({
  useInfiniteRecommendations: (...args: unknown[]) =>
    mockUseInfiniteRecommendations(...args),
}));

vi.mock("@/hooks/useGroupedGenres", () => ({
  useGroupedGenres: () => mockUseGroupedGenres(),
}));

vi.mock("@/hooks/useMyList", () => ({
  useMyListIds: () => ({ data: new Set<number>(), isLoading: false }),
  useAddToList: () => ({ mutate: vi.fn(), isPending: false }),
  useRemoveFromList: () => ({ mutate: vi.fn(), isPending: false }),
}));

// -- Test data ---------------------------------------------------------------

const mockProfile: UserProfile = {
  id: 10,
  username: "reader",
  rating_count: 8,
  list_count: 2,
};

const mockBook: Book = {
  id: 1,
  title: "Test Book",
  author_id: 1,
  publisher_id: 1,
  publish_date: "2024-01-01",
  description: "A test book.",
  url: "https://example.com",
  cover: null,
  author: { id: 1, name: "Test Author" },
  publisher: { id: 1, name: "Test Publisher" },
  genres: [{ id: 1, name: "Fiction" }],
  avg_critic_rating: 3.0,
  review_count: 5,
};

const mockFictionPage: PaginatedRecommendationResponse = {
  items: [{ ...mockBook, id: 2, title: "Recommended Fiction" }],
  meta: { strategy: "personalized", rating_count: 8, category: "fiction" },
  total: 1,
  offset: 0,
  limit: 20,
  has_more: false,
};

const mockNonfictionPage: PaginatedRecommendationResponse = {
  items: [{ ...mockBook, id: 3, title: "Recommended Nonfiction" }],
  meta: { strategy: "personalized", rating_count: 8, category: "nonfiction" },
  total: 1,
  offset: 0,
  limit: 20,
  has_more: false,
};

// -- Helpers -----------------------------------------------------------------

function renderProfilePage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/profile"]}>
        <Routes>
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/login" element={<div>Login Page</div>} />
          <Route path="/" element={<div>Home Page</div>} />
          <Route path="/ratings" element={<div>My Ratings Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function makeInfiniteResult(page: PaginatedRecommendationResponse) {
  return {
    data: { pages: [page], pageParams: [0] },
    isLoading: false,
    isFetchingNextPage: false,
    hasNextPage: page.has_more,
    fetchNextPage: vi.fn(),
  };
}

function setupAuthenticatedMocks(overrides?: {
  ratingCount?: number;
  fictionPage?: PaginatedRecommendationResponse;
  nonfictionPage?: PaginatedRecommendationResponse;
}) {
  const {
    ratingCount = 8,
    fictionPage = mockFictionPage,
    nonfictionPage = mockNonfictionPage,
  } = overrides ?? {};

  mockUseAuth.mockReturnValue({
    user: { id: 10, username: "reader" },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    getAccessToken: vi.fn(),
  });

  mockUseUserProfile.mockReturnValue({
    data: { ...mockProfile, rating_count: ratingCount },
    isLoading: false,
  });

  mockUseGroupedGenres.mockReturnValue({
    data: {
      fiction: [{ id: 1, name: "Mystery" }],
      nonfiction: [{ id: 2, name: "History" }],
      unknown: [],
    },
    isLoading: false,
  });

  mockUseInfiniteRecommendations.mockImplementation(
    ({ category }: { category: string }) => {
      if (category === "fiction") return makeInfiniteResult(fictionPage);
      if (category === "nonfiction") return makeInfiniteResult(nonfictionPage);
      return {
        data: undefined,
        isLoading: false,
        isFetchingNextPage: false,
        hasNextPage: false,
        fetchNextPage: vi.fn(),
      };
    }
  );
}

// -- Tests -------------------------------------------------------------------

describe("ProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects to /login when user is not authenticated", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserProfile.mockReturnValue({ data: undefined, isLoading: false });
    mockUseInfiniteRecommendations.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetchingNextPage: false,
      hasNextPage: false,
      fetchNextPage: vi.fn(),
    });

    renderProfilePage();

    expect(screen.getByText("Login Page")).toBeInTheDocument();
  });

  it("shows loading state while auth is loading", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserProfile.mockReturnValue({ data: undefined, isLoading: false });
    mockUseInfiniteRecommendations.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetchingNextPage: false,
      hasNextPage: false,
      fetchNextPage: vi.fn(),
    });

    const { container } = renderProfilePage();

    const skeletons = container.querySelectorAll(".skeleton-shimmer");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows loading state while profile data is being fetched", () => {
    mockUseAuth.mockReturnValue({
      user: { id: 10, username: "reader" },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });

    mockUseUserProfile.mockReturnValue({ data: undefined, isLoading: true });
    mockUseInfiniteRecommendations.mockReturnValue({
      data: undefined,
      isLoading: true,
      isFetchingNextPage: false,
      hasNextPage: false,
      fetchNextPage: vi.fn(),
    });

    const { container } = renderProfilePage();

    const skeletons = container.querySelectorAll(".skeleton-shimmer");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows page title 'Recommended for You'", () => {
    setupAuthenticatedMocks();

    renderProfilePage();

    expect(
      screen.getByRole("heading", { level: 1 })
    ).toHaveTextContent("Recommended for You");
  });

  it("does not show 'My Rated Books' section", () => {
    setupAuthenticatedMocks();

    renderProfilePage();

    expect(screen.queryByText("My Rated Books")).not.toBeInTheDocument();
  });

  it("shows a link to the My Ratings page", () => {
    setupAuthenticatedMocks();

    renderProfilePage();

    const ratingsLink = screen.getByRole("link", { name: /my ratings/i });
    expect(ratingsLink).toBeInTheDocument();
    expect(ratingsLink).toHaveAttribute("href", "/ratings");
  });

  it("shows 'rate more books' message when user has 1-4 ratings", () => {
    setupAuthenticatedMocks({ ratingCount: 2 });

    renderProfilePage();

    expect(screen.getByText(/rate 3 more books/i)).toBeInTheDocument();
  });

  it("shows recommendation tabs when user has 5+ ratings", () => {
    setupAuthenticatedMocks();

    renderProfilePage();

    expect(
      screen.getByRole("tab", { name: /^fiction$/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /^non-fiction$/i })
    ).toBeInTheDocument();
  });

  it("shows prompt to rate books when user has 0 ratings", () => {
    setupAuthenticatedMocks({ ratingCount: 0 });

    renderProfilePage();

    expect(screen.getByText(/rate 5 more books/i)).toBeInTheDocument();
  });

  it("shows rating count in subtitle", () => {
    setupAuthenticatedMocks({ ratingCount: 8 });

    renderProfilePage();

    expect(screen.getByText(/8 books rated/i)).toBeInTheDocument();
  });

  it("shows singular text for 1 book rated", () => {
    setupAuthenticatedMocks({ ratingCount: 1 });

    renderProfilePage();

    expect(screen.getByText(/1 book rated/i)).toBeInTheDocument();
  });
});

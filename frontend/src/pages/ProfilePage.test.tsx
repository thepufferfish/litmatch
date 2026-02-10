import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProfilePage } from "./ProfilePage";
import type { Book, PaginatedResponse, RecommendationResponse, UserProfile, UserRating } from "@/types";

// -- Mocks -------------------------------------------------------------------

const mockUseAuth = vi.fn();
const mockUseUserProfile = vi.fn();
const mockUseRecommendations = vi.fn();
const mockUseUserRatedBooks = vi.fn();
const mockUseUserRatings = vi.fn();

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("@/hooks/useUserProfile", () => ({
  useUserProfile: (...args: unknown[]) => mockUseUserProfile(...args),
}));

vi.mock("@/hooks/useRecommendations", () => ({
  useRecommendations: (...args: unknown[]) => mockUseRecommendations(...args),
}));

vi.mock("@/hooks/useUserRatedBooks", () => ({
  useUserRatedBooks: (...args: unknown[]) => mockUseUserRatedBooks(...args),
  useUserRatings: (...args: unknown[]) => mockUseUserRatings(...args),
}));

// -- Test data ---------------------------------------------------------------

const mockProfile: UserProfile = {
  id: 10,
  username: "reader",
  rating_count: 8,
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

const mockRating: UserRating = {
  id: 1,
  user_id: 10,
  book_id: 1,
  rating: 4,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const mockBooksResponse: PaginatedResponse<Book> = {
  items: [mockBook],
  total: 1,
  page: 1,
  limit: 100,
};

const mockFictionRecommendations: RecommendationResponse = {
  items: [{ ...mockBook, id: 2, title: "Recommended Fiction" }],
  meta: { strategy: "personalized", rating_count: 8, category: "fiction" },
};

const mockNonfictionRecommendations: RecommendationResponse = {
  items: [{ ...mockBook, id: 3, title: "Recommended Nonfiction" }],
  meta: { strategy: "personalized", rating_count: 8, category: "nonfiction" },
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
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function setupAuthenticatedMocks(overrides?: {
  ratingCount?: number;
  ratedBooks?: PaginatedResponse<Book>;
  ratings?: UserRating[];
  fictionRecs?: RecommendationResponse;
  nonfictionRecs?: RecommendationResponse;
}) {
  const {
    ratingCount = 8,
    ratedBooks = mockBooksResponse,
    ratings = [mockRating],
    fictionRecs = mockFictionRecommendations,
    nonfictionRecs = mockNonfictionRecommendations,
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

  mockUseUserRatedBooks.mockReturnValue({
    data: ratedBooks,
    isLoading: false,
  });

  mockUseUserRatings.mockReturnValue({
    data: ratings,
    isLoading: false,
  });

  mockUseRecommendations.mockImplementation(({ category }: { category: string }) => {
    if (category === "fiction") return { data: fictionRecs, isLoading: false };
    if (category === "nonfiction") return { data: nonfictionRecs, isLoading: false };
    return { data: undefined, isLoading: false };
  });
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
    mockUseUserRatedBooks.mockReturnValue({ data: undefined, isLoading: false });
    mockUseUserRatings.mockReturnValue({ data: undefined, isLoading: false });
    mockUseRecommendations.mockReturnValue({ data: undefined, isLoading: false });

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
    mockUseUserRatedBooks.mockReturnValue({ data: undefined, isLoading: false });
    mockUseUserRatings.mockReturnValue({ data: undefined, isLoading: false });
    mockUseRecommendations.mockReturnValue({ data: undefined, isLoading: false });

    const { container } = renderProfilePage();

    const skeletons = container.querySelectorAll(".skeleton-shimmer");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows 'no ratings' empty state when user has 0 ratings", () => {
    setupAuthenticatedMocks({
      ratingCount: 0,
      ratedBooks: { items: [], total: 0, page: 1, limit: 100 },
      ratings: [],
    });

    renderProfilePage();

    expect(
      screen.getByText(/haven't rated any books yet/i)
    ).toBeInTheDocument();
  });

  it("shows 'rate more books' message when user has 1-4 ratings", () => {
    setupAuthenticatedMocks({ ratingCount: 2 });

    renderProfilePage();

    expect(
      screen.getByText(/rate 3 more books/i)
    ).toBeInTheDocument();
  });

  it("shows rated books grid with star ratings", () => {
    setupAuthenticatedMocks();

    renderProfilePage();

    expect(screen.getByText("My Rated Books")).toBeInTheDocument();
    expect(screen.getByText("Test Book")).toBeInTheDocument();
  });

  it("shows recommendation tabs when user has 5+ ratings", () => {
    setupAuthenticatedMocks();

    renderProfilePage();

    expect(screen.getByText("Recommended for You")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /^fiction$/i })).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /^non-fiction$/i })
    ).toBeInTheDocument();
  });

  it("shows the user rating overlaid on book cards", () => {
    setupAuthenticatedMocks();

    renderProfilePage();

    // The star rating display should show "4/5" for the rated book
    expect(screen.getByText("4/5")).toBeInTheDocument();
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
    mockUseUserRatedBooks.mockReturnValue({ data: undefined, isLoading: true });
    mockUseUserRatings.mockReturnValue({ data: undefined, isLoading: true });
    mockUseRecommendations
      .mockReturnValueOnce({ data: undefined, isLoading: true })
      .mockReturnValueOnce({ data: undefined, isLoading: true });

    const { container } = renderProfilePage();

    const skeletons = container.querySelectorAll(".skeleton-shimmer");
    expect(skeletons.length).toBeGreaterThan(0);
  });
});

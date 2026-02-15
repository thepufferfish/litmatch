import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProfilePage } from "./ProfilePage";
import type { Book, RecommendationResponse, UserProfile } from "@/types";

// -- Mocks -------------------------------------------------------------------

const mockUseAuth = vi.fn();
const mockUseUserProfile = vi.fn();
const mockUseRecommendations = vi.fn();

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("@/hooks/useUserProfile", () => ({
  useUserProfile: (...args: unknown[]) => mockUseUserProfile(...args),
}));

vi.mock("@/hooks/useRecommendations", () => ({
  useRecommendations: (...args: unknown[]) => mockUseRecommendations(...args),
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
          <Route path="/ratings" element={<div>My Ratings Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function setupAuthenticatedMocks(overrides?: {
  ratingCount?: number;
  fictionRecs?: RecommendationResponse;
  nonfictionRecs?: RecommendationResponse;
}) {
  const {
    ratingCount = 8,
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

  mockUseRecommendations.mockImplementation(
    ({ category }: { category: string }) => {
      if (category === "fiction")
        return { data: fictionRecs, isLoading: false };
      if (category === "nonfiction")
        return { data: nonfictionRecs, isLoading: false };
      return { data: undefined, isLoading: false };
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
    mockUseRecommendations.mockReturnValue({
      data: undefined,
      isLoading: false,
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
    mockUseRecommendations.mockReturnValue({
      data: undefined,
      isLoading: false,
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
    mockUseRecommendations
      .mockReturnValueOnce({ data: undefined, isLoading: true })
      .mockReturnValueOnce({ data: undefined, isLoading: true });

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

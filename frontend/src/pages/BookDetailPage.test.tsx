import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BookDetailPage } from "./BookDetailPage";
import type { Book, UserRating } from "@/types";

// ── Mocks ────────────────────────────────────────────────────────────

const mockBook: Book = {
  id: 42,
  title: "Test Book",
  author_id: 1,
  publisher_id: 1,
  publish_date: "2024-01-01",
  description: "A test book.",
  url: "https://example.com",
  cover: null,
  author: { id: 1, name: "Jane Author" },
  publisher: { id: 1, name: "Test Press" },
  genres: [{ id: 1, name: "Fiction" }],
  avg_critic_rating: 3.2,
  review_count: 8,
};

const mockRating: UserRating = {
  id: 1,
  user_id: 10,
  book_id: 42,
  rating: 4,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

// Mock hooks
const mockUseBook = vi.fn();
const mockUseReviews = vi.fn();
const mockUseUserRating = vi.fn();
const mockSubmitRating = vi.fn();
const mockDeleteRating = vi.fn();
const mockUseAuth = vi.fn();

vi.mock("@/hooks/useBooks", () => ({
  useBook: (...args: unknown[]) => mockUseBook(...args),
}));

vi.mock("@/hooks/useReviews", () => ({
  useReviews: (...args: unknown[]) => mockUseReviews(...args),
}));

vi.mock("@/hooks/useRatings", () => ({
  useUserRating: (...args: unknown[]) => mockUseUserRating(...args),
  useSubmitRating: (_userId?: number) => ({
    mutate: mockSubmitRating,
    isPending: false,
  }),
  useDeleteRating: (_userId?: number) => ({
    mutate: mockDeleteRating,
    isPending: false,
  }),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("@/hooks/useMyList", () => ({
  useMyListIds: () => ({ data: new Set<number>(), isLoading: false }),
  useAddToList: () => ({ mutate: vi.fn(), isPending: false }),
  useRemoveFromList: () => ({ mutate: vi.fn(), isPending: false }),
}));

// ── Helpers ──────────────────────────────────────────────────────────

function renderWithProviders(bookId = "42") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/books/${bookId}`]}>
        <Routes>
          <Route path="/books/:id" element={<BookDetailPage />} />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function setupDefaultMocks(overrides?: {
  isAuthenticated?: boolean;
  user?: { id: number; username: string } | null;
  existingRating?: UserRating | null;
}) {
  const {
    isAuthenticated = false,
    user = null,
    existingRating = null,
  } = overrides ?? {};

  mockUseBook.mockReturnValue({
    data: mockBook,
    isLoading: false,
    error: null,
  });

  mockUseReviews.mockReturnValue({
    data: [],
    isLoading: false,
  });

  mockUseAuth.mockReturnValue({
    user,
    isAuthenticated,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    getAccessToken: vi.fn(),
  });

  mockUseUserRating.mockReturnValue({
    data: existingRating,
    isLoading: false,
  });
}

// ── Tests ────────────────────────────────────────────────────────────

describe("BookDetailPage - Core rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows 'Book not found' when book data is null (error state)", () => {
    mockUseBook.mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error("Not found"),
    });
    mockUseReviews.mockReturnValue({ data: [], isLoading: false });
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserRating.mockReturnValue({ data: null, isLoading: false });

    renderWithProviders();

    expect(screen.getByText("Book not found")).toBeInTheDocument();
    expect(
      screen.getByText(/doesn.t exist or has been removed/i)
    ).toBeInTheDocument();
  });

  it("shows 'Book not found' when there is an error and no data", () => {
    mockUseBook.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: { message: "Network error" },
    });
    mockUseReviews.mockReturnValue({ data: [], isLoading: false });
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserRating.mockReturnValue({ data: null, isLoading: false });

    renderWithProviders();

    expect(screen.getByText("Book not found")).toBeInTheDocument();
  });

  it("renders book title and author when data loads successfully", () => {
    setupDefaultMocks();

    renderWithProviders();

    expect(screen.getByText("Test Book")).toBeInTheDocument();
    expect(screen.getByText("Jane Author")).toBeInTheDocument();
  });

  it("renders publisher name", () => {
    setupDefaultMocks();

    renderWithProviders();

    expect(screen.getByText("Test Press")).toBeInTheDocument();
  });

  it("renders book description", () => {
    setupDefaultMocks();

    renderWithProviders();

    expect(screen.getByText("A test book.")).toBeInTheDocument();
  });

  it("renders 'No description available' when description is empty", () => {
    mockUseBook.mockReturnValue({
      data: { ...mockBook, description: "" },
      isLoading: false,
      error: null,
    });
    mockUseReviews.mockReturnValue({ data: [], isLoading: false });
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserRating.mockReturnValue({ data: null, isLoading: false });

    renderWithProviders();

    expect(screen.getByText("No description available.")).toBeInTheDocument();
  });

  it("renders cover image when book has a cover", () => {
    mockUseBook.mockReturnValue({
      data: { ...mockBook, cover: "https://example.com/cover.jpg" },
      isLoading: false,
      error: null,
    });
    mockUseReviews.mockReturnValue({ data: [], isLoading: false });
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserRating.mockReturnValue({ data: null, isLoading: false });

    renderWithProviders();

    const img = screen.getByAltText("Cover of Test Book");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://example.com/cover.jpg");
  });

  it("renders genre links", () => {
    setupDefaultMocks();

    renderWithProviders();

    const genreLink = screen.getByText("Fiction");
    expect(genreLink.closest("a")).toHaveAttribute("href", "/genre/fiction");
  });

  it("renders 'Back to browsing' button", () => {
    setupDefaultMocks();

    renderWithProviders();

    expect(screen.getByText("Back to browsing")).toBeInTheDocument();
  });

  it("renders publish date formatted as a readable string", () => {
    setupDefaultMocks();

    renderWithProviders();

    // The exact date string depends on the timezone of the test runner.
    // "2024-01-01" may render as "January 1, 2024" or "December 31, 2023"
    // depending on UTC offset. We just verify some date text is present.
    const dateText = screen.getByText(/202[34]/);
    expect(dateText).toBeInTheDocument();
  });

  it("renders 'Unknown Author' when author is null", () => {
    mockUseBook.mockReturnValue({
      data: { ...mockBook, author: null },
      isLoading: false,
      error: null,
    });
    mockUseReviews.mockReturnValue({ data: [], isLoading: false });
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserRating.mockReturnValue({ data: null, isLoading: false });

    renderWithProviders();

    expect(screen.getByText("Unknown Author")).toBeInTheDocument();
  });

  it("shows existing rating text when user has rated", () => {
    setupDefaultMocks({
      isAuthenticated: true,
      user: { id: 10, username: "reader" },
      existingRating: mockRating,
    });

    renderWithProviders();

    expect(screen.getByText("You rated this 4/5")).toBeInTheDocument();
  });

  it("renders review count in critic reviews heading", () => {
    mockUseBook.mockReturnValue({
      data: mockBook,
      isLoading: false,
      error: null,
    });
    mockUseReviews.mockReturnValue({
      data: [
        {
          id: 1,
          book_id: 42,
          rating: 4,
          review: "Great book",
          url: "https://example.com",
          critic: { id: 1, name: "Critic" },
          publication: null,
        },
        {
          id: 2,
          book_id: 42,
          rating: 3,
          review: "Good book",
          url: "https://example.com",
          critic: { id: 2, name: "Other Critic" },
          publication: null,
        },
      ],
      isLoading: false,
    });
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserRating.mockReturnValue({ data: null, isLoading: false });

    renderWithProviders();

    expect(screen.getByText("(2)")).toBeInTheDocument();
  });

  it("shows reviews loading skeleton when reviews are loading", () => {
    mockUseBook.mockReturnValue({
      data: mockBook,
      isLoading: false,
      error: null,
    });
    mockUseReviews.mockReturnValue({
      data: undefined,
      isLoading: true,
    });
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserRating.mockReturnValue({ data: null, isLoading: false });

    const { container } = renderWithProviders();

    // Should have skeleton shimmer elements for reviews
    const skeletons = container.querySelectorAll(".skeleton-shimmer");
    expect(skeletons.length).toBeGreaterThan(0);
  });
});

describe("BookDetailPage - Rating Section", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows login prompt when user is not authenticated", () => {
    setupDefaultMocks({ isAuthenticated: false, user: null });

    renderWithProviders();

    expect(screen.getByText("Your Rating")).toBeInTheDocument();
    expect(screen.getByText(/log in to rate/i)).toBeInTheDocument();
    const loginLinks = screen.getAllByRole("link", { name: /log in/i });
    expect(loginLinks.length).toBeGreaterThanOrEqual(1);
    expect(loginLinks[0]).toHaveAttribute("href", "/login");
  });

  it("shows interactive star rating when user is authenticated", () => {
    setupDefaultMocks({
      isAuthenticated: true,
      user: { id: 10, username: "reader" },
      existingRating: null,
    });

    renderWithProviders();

    expect(screen.getByText("Your Rating")).toBeInTheDocument();
    // Should show interactive stars (buttons)
    const starButtons = screen.getAllByRole("button", { name: /rate \d star/i });
    expect(starButtons).toHaveLength(5);
  });

  it("shows existing rating value when user has already rated", () => {
    setupDefaultMocks({
      isAuthenticated: true,
      user: { id: 10, username: "reader" },
      existingRating: mockRating,
    });

    renderWithProviders();

    // Stars 1-4 should be filled, star 5 should not (rating is 4)
    for (let i = 1; i <= 4; i++) {
      const star = screen.getByTestId(`star-${i}`);
      expect(star).toHaveAttribute("data-filled", "true");
    }
    const star5 = screen.getByTestId("star-5");
    expect(star5).toHaveAttribute("data-filled", "false");
  });

  it("submits rating when user clicks a star", async () => {
    const user = userEvent.setup();
    setupDefaultMocks({
      isAuthenticated: true,
      user: { id: 10, username: "reader" },
      existingRating: null,
    });

    renderWithProviders();

    const star3 = screen.getByRole("button", { name: /rate 3 star/i });
    await user.click(star3);

    expect(mockSubmitRating).toHaveBeenCalledWith({ book_id: 42, rating: 3 });
  });

  it("does not show rating section while book is loading", () => {
    mockUseBook.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });
    mockUseReviews.mockReturnValue({ data: [], isLoading: false });
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserRating.mockReturnValue({ data: null, isLoading: false });

    renderWithProviders();

    // Should show skeleton, not rating section
    expect(screen.queryByText("Your Rating")).not.toBeInTheDocument();
  });

  it("shows rating loading state while fetching existing rating", () => {
    setupDefaultMocks({
      isAuthenticated: true,
      user: { id: 10, username: "reader" },
    });
    mockUseUserRating.mockReturnValue({
      data: null,
      isLoading: true,
    });

    renderWithProviders();

    expect(screen.getByText("Your Rating")).toBeInTheDocument();
    // Should show a loading indicator for the rating
    expect(screen.getByTestId("rating-loading")).toBeInTheDocument();
  });

  it("passes the correct user id to useUserRating", () => {
    setupDefaultMocks({
      isAuthenticated: true,
      user: { id: 10, username: "reader" },
    });

    renderWithProviders();

    expect(mockUseUserRating).toHaveBeenCalledWith(42, 10);
  });

  it("passes undefined user id to useUserRating when not authenticated", () => {
    setupDefaultMocks({
      isAuthenticated: false,
      user: null,
    });

    renderWithProviders();

    expect(mockUseUserRating).toHaveBeenCalledWith(42, undefined);
  });

  it("shows Remove button when user has existing rating", () => {
    setupDefaultMocks({
      isAuthenticated: true,
      user: { id: 10, username: "reader" },
      existingRating: mockRating,
    });

    renderWithProviders();

    expect(screen.getByText("Remove")).toBeInTheDocument();
  });

  it("calls deleteRating when Remove button is clicked", async () => {
    const user = userEvent.setup();
    setupDefaultMocks({
      isAuthenticated: true,
      user: { id: 10, username: "reader" },
      existingRating: mockRating,
    });

    renderWithProviders();

    await user.click(screen.getByText("Remove"));

    expect(mockDeleteRating).toHaveBeenCalledWith(42);
  });

  it("does not show Remove button when no rating exists", () => {
    setupDefaultMocks({
      isAuthenticated: true,
      user: { id: 10, username: "reader" },
      existingRating: null,
    });

    renderWithProviders();

    expect(screen.queryByText("Remove")).not.toBeInTheDocument();
  });
});

describe("BookDetailPage - Average Critic Rating", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows critic rating badge when avg_critic_rating is present", () => {
    setupDefaultMocks();

    renderWithProviders();

    expect(screen.getByTestId("critic-rating-badge")).toBeInTheDocument();
    expect(screen.getByText(/3\.2/)).toBeInTheDocument();
  });

  it("shows review count text on detail page", () => {
    setupDefaultMocks();

    renderWithProviders();

    expect(screen.getByText("from 8 reviews")).toBeInTheDocument();
  });

  it("does not show critic rating badge when avg_critic_rating is null", () => {
    mockUseBook.mockReturnValue({
      data: { ...mockBook, avg_critic_rating: null, review_count: 0 },
      isLoading: false,
      error: null,
    });
    mockUseReviews.mockReturnValue({ data: [], isLoading: false });
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserRating.mockReturnValue({ data: null, isLoading: false });

    renderWithProviders();

    expect(screen.queryByTestId("critic-rating-badge")).not.toBeInTheDocument();
  });
});

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
const mockUseAuth = vi.fn();

vi.mock("@/hooks/useBooks", () => ({
  useBook: (...args: unknown[]) => mockUseBook(...args),
}));

vi.mock("@/hooks/useReviews", () => ({
  useReviews: (...args: unknown[]) => mockUseReviews(...args),
}));

vi.mock("@/hooks/useRatings", () => ({
  useUserRating: (...args: unknown[]) => mockUseUserRating(...args),
  useSubmitRating: () => ({
    mutate: mockSubmitRating,
    isPending: false,
  }),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
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

describe("BookDetailPage - Rating Section", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows login prompt when user is not authenticated", () => {
    setupDefaultMocks({ isAuthenticated: false, user: null });

    renderWithProviders();

    expect(screen.getByText("Your Rating")).toBeInTheDocument();
    expect(screen.getByText(/log in to rate/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /log in/i })).toHaveAttribute(
      "href",
      "/login"
    );
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
});

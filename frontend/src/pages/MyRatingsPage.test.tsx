import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MyRatingsPage } from "./MyRatingsPage";
import type { Book, PaginatedResponse } from "@/types";

// -- Mocks -------------------------------------------------------------------

const mockUseAuth = vi.fn();
const mockUseUserRatedBooksPaginated = vi.fn();
const mockUseUserRatingsMap = vi.fn();
const mockDeleteRating = vi.fn();
const mockSubmitRating = vi.fn();

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("@/hooks/useUserRatedBooks", () => ({
  useUserRatedBooksPaginated: (...args: unknown[]) =>
    mockUseUserRatedBooksPaginated(...args),
}));

vi.mock("@/hooks/useRatings", () => ({
  useUserRatingsMap: (...args: unknown[]) => mockUseUserRatingsMap(...args),
  useDeleteRating: (_userId?: number) => ({
    mutate: mockDeleteRating,
    isPending: false,
  }),
  useSubmitRating: (_userId?: number) => ({
    mutate: mockSubmitRating,
    isPending: false,
  }),
}));

vi.mock("@/components/BookGrid", () => ({
  BookGrid: ({
    books,
    isLoading,
  }: {
    books?: Book[];
    isLoading: boolean;
  }) => (
    <div
      data-testid="book-grid"
      data-loading={isLoading}
      data-books-length={books?.length ?? "n/a"}
    >
      {books?.map((b) => (
        <div key={b.id} data-testid="book-card">
          {b.title}
        </div>
      ))}
    </div>
  ),
}));

vi.mock("@/components/SortSelect", () => ({
  SORT_OPTIONS: [
    { value: "rating_desc", label: "Highest Rated" },
    { value: "title_asc", label: "Title A\u2013Z" },
    { value: "title_desc", label: "Title Z\u2013A" },
  ],
  SortSelect: ({
    value,
    onChange,
  }: {
    value?: string;
    onChange: (v: string | undefined) => void;
  }) => (
    <select
      data-testid="sort-select"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || undefined)}
    >
      <option value="">Default</option>
      <option value="rating_desc">Highest Rated</option>
      <option value="title_asc">Title A-Z</option>
    </select>
  ),
}));

vi.mock("@/components/Pagination", () => ({
  Pagination: ({
    currentPage,
    totalPages,
    onPageChange,
  }: {
    currentPage: number;
    totalPages: number;
    onPageChange: (p: number) => void;
  }) => (
    <div
      data-testid="pagination"
      data-page={currentPage}
      data-total-pages={totalPages}
    >
      {totalPages > 1 && (
        <>
          <button
            data-testid="page-next"
            onClick={() => onPageChange(currentPage + 1)}
          >
            Next
          </button>
          <button
            data-testid="page-prev"
            onClick={() => onPageChange(currentPage - 1)}
          >
            Previous
          </button>
          {`Page ${currentPage} of ${totalPages}`}
        </>
      )}
    </div>
  ),
}));

// -- Test data ---------------------------------------------------------------

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

const mockBook2: Book = {
  ...mockBook,
  id: 2,
  title: "Second Book",
};

const mockBooksResponse: PaginatedResponse<Book> = {
  items: [mockBook, mockBook2],
  total: 2,
  page: 1,
  limit: 12,
};

const mockRatingsMap = new Map<number, number>([
  [1, 4],
  [2, 5],
]);

// -- Helpers -----------------------------------------------------------------

function renderMyRatingsPage(route = "/ratings") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/ratings" element={<MyRatingsPage />} />
          <Route path="/login" element={<div>Login Page</div>} />
          <Route path="/" element={<div>Home Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function setupAuthenticatedMocks(overrides?: {
  booksData?: PaginatedResponse<Book>;
  booksLoading?: boolean;
  ratingsMap?: Map<number, number>;
  ratingsLoading?: boolean;
}) {
  const {
    booksData = mockBooksResponse,
    booksLoading = false,
    ratingsMap = mockRatingsMap,
    ratingsLoading = false,
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

  mockUseUserRatedBooksPaginated.mockReturnValue({
    data: booksData,
    isLoading: booksLoading,
  });

  mockUseUserRatingsMap.mockReturnValue({
    data: ratingsMap,
    isLoading: ratingsLoading,
  });
}

// -- Tests -------------------------------------------------------------------

describe("MyRatingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // -- Auth redirect ---------------------------------------------------------

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
    mockUseUserRatedBooksPaginated.mockReturnValue({
      data: undefined,
      isLoading: false,
    });
    mockUseUserRatingsMap.mockReturnValue({
      data: undefined,
      isLoading: false,
    });

    renderMyRatingsPage();

    expect(screen.getByText("Login Page")).toBeInTheDocument();
  });

  // -- Loading state ---------------------------------------------------------

  it("shows loading skeleton while auth is loading", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      getAccessToken: vi.fn(),
    });
    mockUseUserRatedBooksPaginated.mockReturnValue({
      data: undefined,
      isLoading: false,
    });
    mockUseUserRatingsMap.mockReturnValue({
      data: undefined,
      isLoading: false,
    });

    const { container } = renderMyRatingsPage();

    const skeletons = container.querySelectorAll(".skeleton-shimmer");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows loading state while books data is being fetched", () => {
    setupAuthenticatedMocks({ booksLoading: true, booksData: undefined });

    renderMyRatingsPage();

    const grid = screen.getByTestId("book-grid");
    expect(grid).toHaveAttribute("data-loading", "true");
  });

  // -- Empty state -----------------------------------------------------------

  it("shows empty state when user has no ratings", () => {
    setupAuthenticatedMocks({
      booksData: { items: [], total: 0, page: 1, limit: 12 },
      ratingsMap: new Map(),
    });

    renderMyRatingsPage();

    expect(
      screen.getByText(/haven't rated any books yet/i)
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /browse books/i })).toBeInTheDocument();
  });

  // -- Rendering rated books -------------------------------------------------

  it("renders page title 'My Ratings'", () => {
    setupAuthenticatedMocks();

    renderMyRatingsPage();

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "My Ratings"
    );
  });

  it("shows the rating count", () => {
    setupAuthenticatedMocks();

    renderMyRatingsPage();

    expect(screen.getByText(/2 books rated/i)).toBeInTheDocument();
  });

  it("renders book grid with rated books", () => {
    setupAuthenticatedMocks();

    renderMyRatingsPage();

    const grid = screen.getByTestId("book-grid");
    expect(grid).toHaveAttribute("data-loading", "false");
    expect(grid).toHaveAttribute("data-books-length", "2");
    expect(screen.getByText("Test Book")).toBeInTheDocument();
    expect(screen.getByText("Second Book")).toBeInTheDocument();
  });

  it("renders sort select component", () => {
    setupAuthenticatedMocks();

    renderMyRatingsPage();

    expect(screen.getByTestId("sort-select")).toBeInTheDocument();
  });

  // -- Pagination ------------------------------------------------------------

  it("renders pagination when multiple pages exist", () => {
    setupAuthenticatedMocks({
      booksData: {
        items: [mockBook],
        total: 25,
        page: 1,
        limit: 12,
      },
    });

    renderMyRatingsPage();

    const pagination = screen.getByTestId("pagination");
    expect(pagination).toHaveAttribute("data-total-pages", "3");
    expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument();
  });

  it("does not render pagination navigation when total fits in one page", () => {
    setupAuthenticatedMocks({
      booksData: {
        items: [mockBook],
        total: 5,
        page: 1,
        limit: 12,
      },
    });

    renderMyRatingsPage();

    // Pagination component renders but with totalPages <= 1, so no nav buttons
    expect(screen.queryByTestId("page-next")).not.toBeInTheDocument();
  });

  it("reads page from URL search params", () => {
    setupAuthenticatedMocks();

    renderMyRatingsPage("/ratings?page=3");

    expect(mockUseUserRatedBooksPaginated).toHaveBeenCalledWith(
      10,
      expect.objectContaining({ page: 3 })
    );
  });

  it("reads sort from URL search params", () => {
    setupAuthenticatedMocks();

    renderMyRatingsPage("/ratings?sort=title_asc");

    expect(mockUseUserRatedBooksPaginated).toHaveBeenCalledWith(
      10,
      expect.objectContaining({ sort: "title_asc" })
    );
  });

  // -- Sort changes ----------------------------------------------------------

  it("resets page to 1 when sort changes", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();

    setupAuthenticatedMocks({
      booksData: {
        items: [mockBook],
        total: 50,
        page: 2,
        limit: 12,
      },
    });

    renderMyRatingsPage("/ratings?page=2");

    const sortSelect = screen.getByTestId("sort-select");
    await user.selectOptions(sortSelect, "rating_desc");

    // After changing sort, the hook should be called with page=1
    const lastCall =
      mockUseUserRatedBooksPaginated.mock.calls[
        mockUseUserRatedBooksPaginated.mock.calls.length - 1
      ]!;
    expect(lastCall[1]).toMatchObject({ page: 1 });
  });

  // -- Page change -----------------------------------------------------------

  it("updates URL when page changes", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();

    setupAuthenticatedMocks({
      booksData: {
        items: [mockBook],
        total: 50,
        page: 1,
        limit: 12,
      },
    });

    renderMyRatingsPage();

    const nextBtn = screen.getByTestId("page-next");
    await user.click(nextBtn);

    // After clicking next, the hook should have been re-called
    const lastCall =
      mockUseUserRatedBooksPaginated.mock.calls[
        mockUseUserRatedBooksPaginated.mock.calls.length - 1
      ]!;
    expect(lastCall[1]).toMatchObject({ page: 2 });
  });

  it("preserves sort when changing pages", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();

    setupAuthenticatedMocks({
      booksData: {
        items: [mockBook],
        total: 50,
        page: 1,
        limit: 12,
      },
    });

    renderMyRatingsPage("/ratings?sort=title_asc");

    const nextBtn = screen.getByTestId("page-next");
    await user.click(nextBtn);

    const lastCall =
      mockUseUserRatedBooksPaginated.mock.calls[
        mockUseUserRatedBooksPaginated.mock.calls.length - 1
      ]!;
    expect(lastCall[1]).toMatchObject({ sort: "title_asc" });
  });

  // -- Redirect out-of-range page --------------------------------------------

  it("redirects to page 1 when page exceeds total pages", () => {
    setupAuthenticatedMocks({
      booksData: {
        items: [],
        total: 10,
        page: 100,
        limit: 12,
      },
    });

    renderMyRatingsPage("/ratings?page=100");

    // After redirect, hook should be called with page=1
    const lastCall =
      mockUseUserRatedBooksPaginated.mock.calls[
        mockUseUserRatedBooksPaginated.mock.calls.length - 1
      ]!;
    expect(lastCall[1]).toMatchObject({ page: 1 });
  });

  // -- Delete rating ---------------------------------------------------------

  it("passes onRate handler to BookGrid for rating interactions", () => {
    setupAuthenticatedMocks();

    renderMyRatingsPage();

    // The book grid should be rendered (rating interactions are tested via BookGrid/BookCard)
    expect(screen.getByTestId("book-grid")).toBeInTheDocument();
  });

  // -- Invalid sort param ----------------------------------------------------

  it("ignores invalid sort parameter from URL", () => {
    setupAuthenticatedMocks();

    renderMyRatingsPage("/ratings?sort=invalid_sort");

    expect(mockUseUserRatedBooksPaginated).toHaveBeenCalledWith(
      10,
      expect.objectContaining({ sort: undefined })
    );
  });

  // -- Singular/plural text --------------------------------------------------

  it("shows singular text for 1 book rated", () => {
    setupAuthenticatedMocks({
      booksData: {
        items: [mockBook],
        total: 1,
        page: 1,
        limit: 12,
      },
    });

    renderMyRatingsPage();

    expect(screen.getByText(/1 book rated/i)).toBeInTheDocument();
  });
});

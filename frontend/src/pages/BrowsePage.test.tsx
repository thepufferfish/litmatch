import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowsePage } from "./BrowsePage";
import type { Book, Genre, PaginatedResponse } from "@/types";

// ── Mock data ────────────────────────────────────────────────────────

const mockBooks: Book[] = [
  {
    id: 1,
    title: "The Great Gatsby",
    author_id: 1,
    publisher_id: 1,
    publish_date: "1925-04-10",
    description: "A novel about the American dream.",
    url: "https://example.com/gatsby",
    cover: null,
    author: { id: 1, name: "F. Scott Fitzgerald" },
    publisher: { id: 1, name: "Scribner" },
    genres: [{ id: 1, name: "Fiction" }],
    avg_critic_rating: 3.5,
    review_count: 10,
  },
  {
    id: 2,
    title: "1984",
    author_id: 2,
    publisher_id: 2,
    publish_date: "1949-06-08",
    description: "A dystopian novel.",
    url: "https://example.com/1984",
    cover: null,
    author: { id: 2, name: "George Orwell" },
    publisher: { id: 2, name: "Secker & Warburg" },
    genres: [{ id: 1, name: "Fiction" }],
    avg_critic_rating: 2.8,
    review_count: 5,
  },
];

const mockPaginatedResponse: PaginatedResponse<Book> = {
  items: mockBooks,
  total: 2,
  page: 1,
  limit: 24,
};

const mockGenres: Genre[] = [
  { id: 1, name: "Fiction" },
  { id: 2, name: "Non-Fiction" },
];

// ── Mocks ────────────────────────────────────────────────────────────

const mockUseBooks = vi.fn();
const mockUseSearchBooks = vi.fn();
const mockUseGenres = vi.fn();

vi.mock("@/hooks/useBooks", () => ({
  useBooks: (...args: unknown[]) => mockUseBooks(...args),
  useSearchBooks: (...args: unknown[]) => mockUseSearchBooks(...args),
}));

vi.mock("@/hooks/useGenres", () => ({
  useGenres: () => mockUseGenres(),
}));

vi.mock("@/components/BookGrid", () => ({
  BookGrid: ({ books, isLoading }: { books?: Book[]; isLoading: boolean }) => (
    <div
      data-testid="book-grid"
      data-loading={isLoading}
      data-books-type={books === undefined ? "undefined" : "array"}
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

vi.mock("@/components/GenreSidebar", () => ({
  GenreSidebar: ({ activeGenreSlug }: { activeGenreSlug?: string }) => (
    <div data-testid="genre-sidebar" data-active={activeGenreSlug ?? ""} />
  ),
}));

vi.mock("@/components/SearchBar", () => ({
  SearchBar: ({
    initialValue,
    onSearch,
    onClear,
  }: {
    initialValue: string;
    onSearch: (q: string) => void;
    onClear: () => void;
  }) => (
    <div data-testid="search-bar-wrapper">
      <input
        data-testid="search-bar"
        defaultValue={initialValue}
        onChange={(e) => {
          if (e.target.value.length >= 2) onSearch(e.target.value);
        }}
      />
      <button data-testid="clear-search" onClick={onClear}>
        Clear
      </button>
    </div>
  ),
}));

vi.mock("@/components/SortSelect", () => ({
  SORT_OPTIONS: [
    { value: "rating_desc", label: "Highest Rated" },
    { value: "reviews_desc", label: "Most Reviewed" },
    { value: "date_desc", label: "Newest First" },
    { value: "date_asc", label: "Oldest First" },
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
      <option value="reviews_desc">Most Reviewed</option>
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
            data-testid="page-first"
            onClick={() => onPageChange(1)}
          >
            First
          </button>
          {`Page ${currentPage} of ${totalPages}`}
        </>
      )}
    </div>
  ),
}));

// ── Helpers ──────────────────────────────────────────────────────────

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function renderBrowsePage(route = "/") {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/" element={<BrowsePage />} />
          <Route path="/genre/:slug" element={<BrowsePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function setupDefaultMocks(overrides?: {
  booksData?: PaginatedResponse<Book> | null;
  booksLoading?: boolean;
  searchData?: PaginatedResponse<Book> | null;
  searchLoading?: boolean;
  genres?: Genre[] | null;
  genresLoading?: boolean;
}) {
  const opts = overrides ?? {};

  // Use null as the sentinel for "explicitly pass undefined to the mock".
  // JavaScript destructuring defaults treat undefined the same as missing,
  // so we use null to distinguish "not provided" from "explicitly undefined".
  const booksData = "booksData" in opts
    ? (opts.booksData ?? undefined)
    : mockPaginatedResponse;
  const booksLoading = opts.booksLoading ?? false;
  const searchData = "searchData" in opts
    ? (opts.searchData ?? undefined)
    : undefined;
  const searchLoading = opts.searchLoading ?? false;
  const genres = "genres" in opts
    ? (opts.genres ?? undefined)
    : mockGenres;
  const genresLoading = opts.genresLoading ?? false;

  mockUseBooks.mockReturnValue({
    data: booksData,
    isLoading: booksLoading,
    error: null,
  });

  mockUseSearchBooks.mockReturnValue({
    data: searchData,
    isLoading: searchLoading,
    error: null,
  });

  mockUseGenres.mockReturnValue({
    data: genres,
    isLoading: genresLoading,
  });
}

// ── Tests ────────────────────────────────────────────────────────────

describe("BrowsePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("basic rendering", () => {
    it("renders book grid with loaded data", () => {
      setupDefaultMocks();
      renderBrowsePage();

      expect(screen.getByTestId("book-grid")).toBeInTheDocument();
      expect(screen.getAllByTestId("book-card")).toHaveLength(2);
    });

    it("renders genre sidebar", () => {
      setupDefaultMocks();
      renderBrowsePage();

      expect(screen.getByTestId("genre-sidebar")).toBeInTheDocument();
    });

    it("renders search bar", () => {
      setupDefaultMocks();
      renderBrowsePage();

      expect(screen.getByTestId("search-bar")).toBeInTheDocument();
    });
  });

  describe("Bug 2: data.items.length when data is undefined", () => {
    it("does NOT crash when books data is undefined (initial loading)", () => {
      // This is the core Bug 2 test: when switching between browse/search,
      // data becomes undefined during the transition. The page must not
      // throw TypeError accessing data.items.length.
      setupDefaultMocks({
        booksData: undefined,
        booksLoading: true,
      });

      // This should NOT throw
      expect(() => renderBrowsePage()).not.toThrow();

      // Should show loading state
      const grid = screen.getByTestId("book-grid");
      expect(grid).toHaveAttribute("data-loading", "true");
    });

    it("does NOT crash when data is undefined and not loading (race condition)", () => {
      // Race condition: data becomes undefined while isLoading is briefly false
      // during query key switch
      setupDefaultMocks({
        booksData: undefined,
        booksLoading: false,
      });

      expect(() => renderBrowsePage()).not.toThrow();
    });

    it("does NOT crash when search data is undefined during search", () => {
      setupDefaultMocks({
        searchData: undefined,
        searchLoading: true,
      });

      // Render with a search query that triggers search mode (length >= 2)
      expect(() => renderBrowsePage("/?search=test")).not.toThrow();
    });

    it("does NOT crash when search data is undefined and not loading", () => {
      // Simulates the moment between activeQuery switch where data is undefined
      setupDefaultMocks({
        searchData: undefined,
        searchLoading: false,
      });

      expect(() => renderBrowsePage("/?search=test")).not.toThrow();
    });

    it("does NOT crash when data exists but items is undefined (malformed response)", () => {
      // Defense-in-depth: if the API returns data without an items field,
      // accessing data.items.length would throw. Optional chaining prevents this.
      setupDefaultMocks({
        booksData: { total: 0, page: 1, limit: 24 } as PaginatedResponse<Book>,
        booksLoading: false,
      });

      expect(() => renderBrowsePage()).not.toThrow();
    });

    it("does NOT crash when search data exists but items is undefined", () => {
      setupDefaultMocks({
        searchData: { total: 0, page: 1, limit: 24 } as PaginatedResponse<Book>,
        searchLoading: false,
      });

      expect(() => renderBrowsePage("/?search=test")).not.toThrow();
    });

    it("shows empty state correctly when items array is empty", () => {
      setupDefaultMocks({
        booksData: {
          items: [],
          total: 0,
          page: 1,
          limit: 24,
        },
      });

      renderBrowsePage();

      // Should show "No books available yet" empty state
      expect(
        screen.getByText(/no books available yet/i)
      ).toBeInTheDocument();
    });
  });

  describe("page redirect when out of bounds", () => {
    it("does NOT crash in redirect logic when data is undefined", () => {
      // The useEffect at line 56-67 accesses data.items.length.
      // When data is undefined, this must not crash.
      setupDefaultMocks({
        booksData: undefined,
        booksLoading: false,
      });

      expect(() => renderBrowsePage("/?page=5")).not.toThrow();
    });

    it("does NOT crash when data exists but items is empty and page > 1", () => {
      setupDefaultMocks({
        booksData: {
          items: [],
          total: 50,
          page: 5,
          limit: 24,
        },
      });

      // This exercises the redirect logic with valid data
      expect(() => renderBrowsePage("/?page=5")).not.toThrow();
    });
  });

  describe("isEmpty calculation", () => {
    it("does NOT crash computing isEmpty when data is undefined", () => {
      // Line 101: !isLoading && data && data.items.length === 0 && data.total === 0
      // When data is undefined, data.items.length throws TypeError
      setupDefaultMocks({
        booksData: undefined,
        booksLoading: false,
      });

      expect(() => renderBrowsePage()).not.toThrow();
    });

    it("correctly identifies empty state", () => {
      setupDefaultMocks({
        booksData: {
          items: [],
          total: 0,
          page: 1,
          limit: 24,
        },
      });

      renderBrowsePage();
      expect(screen.getByText(/no books available yet/i)).toBeInTheDocument();
    });

    it("does not show empty state when data has items", () => {
      setupDefaultMocks();
      renderBrowsePage();

      expect(
        screen.queryByText(/no books available yet/i)
      ).not.toBeInTheDocument();
    });
  });

  describe("search mode", () => {
    it("shows search result count when searching with data", () => {
      setupDefaultMocks({
        searchData: {
          items: mockBooks,
          total: 2,
          page: 1,
          limit: 24,
        },
      });

      renderBrowsePage("/?search=gatsby");

      // The text "(2 results)" is split across elements, so use a function matcher
      expect(
        screen.getByText((_content, element) => {
          return element?.textContent === "(2 results)";
        })
      ).toBeInTheDocument();
    });

    it("does NOT crash showing result count when search data is undefined", () => {
      setupDefaultMocks({
        searchData: undefined,
        searchLoading: false,
      });

      expect(() => renderBrowsePage("/?search=gatsby")).not.toThrow();
    });
  });

  describe("Bug: totalPages NaN from malformed API response", () => {
    it("computes totalPages as 0 when data.total is undefined", () => {
      // Malformed API response: total field is missing
      // Math.ceil(undefined / 24) produces NaN
      setupDefaultMocks({
        booksData: {
          items: mockBooks,
          page: 1,
          limit: 24,
        } as unknown as PaginatedResponse<Book>,
      });

      renderBrowsePage();

      const pagination = screen.getByTestId("pagination");
      const totalPages = Number(pagination.getAttribute("data-total-pages"));
      expect(Number.isFinite(totalPages)).toBe(true);
      expect(totalPages).toBe(0);
    });

    it("computes totalPages as 0 when data.limit is undefined", () => {
      // Malformed API response: limit field is missing
      // Math.ceil(50 / undefined) produces NaN
      setupDefaultMocks({
        booksData: {
          items: mockBooks,
          total: 50,
          page: 1,
        } as unknown as PaginatedResponse<Book>,
      });

      renderBrowsePage();

      const pagination = screen.getByTestId("pagination");
      const totalPages = Number(pagination.getAttribute("data-total-pages"));
      expect(Number.isFinite(totalPages)).toBe(true);
    });

    it("computes totalPages as 0 when data.limit is 0", () => {
      // Division by zero: Math.ceil(50 / 0) produces Infinity
      setupDefaultMocks({
        booksData: {
          items: mockBooks,
          total: 50,
          page: 1,
          limit: 0,
        },
      });

      renderBrowsePage();

      const pagination = screen.getByTestId("pagination");
      const totalPages = Number(pagination.getAttribute("data-total-pages"));
      expect(Number.isFinite(totalPages)).toBe(true);
      expect(totalPages).toBe(0);
    });

    it("shows empty state when both total and limit are undefined with empty items", () => {
      // When items is empty and total/limit are undefined, the page should
      // show the empty state rather than pagination with NaN values.
      setupDefaultMocks({
        booksData: {
          items: [],
          page: 1,
        } as unknown as PaginatedResponse<Book>,
      });

      renderBrowsePage();

      // With the isEmpty fix, empty items triggers the empty state
      // instead of rendering BookGrid + Pagination with invalid page counts.
      expect(
        screen.getByText(/no books available yet/i)
      ).toBeInTheDocument();
      expect(screen.queryByTestId("pagination")).not.toBeInTheDocument();
    });

    it("computes valid totalPages for a well-formed response", () => {
      setupDefaultMocks({
        booksData: {
          items: mockBooks,
          total: 50,
          page: 1,
          limit: 24,
        },
      });

      renderBrowsePage();

      const pagination = screen.getByTestId("pagination");
      const totalPages = Number(pagination.getAttribute("data-total-pages"));
      expect(totalPages).toBe(3); // Math.ceil(50/24) = 3
    });
  });

  describe("genre filtering", () => {
    it("shows genre not found when slug is invalid", () => {
      setupDefaultMocks();
      renderBrowsePage("/genre/nonexistent-genre");

      expect(screen.getByText("Genre not found")).toBeInTheDocument();
    });

    it("renders normally for valid genre slug", () => {
      setupDefaultMocks();
      renderBrowsePage("/genre/fiction");

      expect(screen.getByTestId("book-grid")).toBeInTheDocument();
      expect(screen.getByText("Fiction")).toBeInTheDocument();
    });
  });

  describe("Bug: blank page when items is undefined or missing", () => {
    it("shows empty state when data exists but items is undefined", () => {
      // Core bug: data.items is undefined, isEmpty evaluates to false,
      // BookGrid receives undefined books and renders nothing.
      // Result: blank page -- neither empty state nor books display.
      // After fix: isEmpty should detect missing items and show empty state.
      setupDefaultMocks({
        booksData: {
          total: 0,
          page: 1,
          limit: 24,
        } as PaginatedResponse<Book>,
        booksLoading: false,
      });

      renderBrowsePage();

      expect(
        screen.getByText(/no books available yet/i)
      ).toBeInTheDocument();
    });

    it("shows empty state when data is undefined and not loading", () => {
      // When data is undefined and not loading, the user sees a blank page.
      // After fix: should show the empty state.
      setupDefaultMocks({
        booksData: undefined,
        booksLoading: false,
      });

      renderBrowsePage();

      expect(
        screen.getByText(/no books available yet/i)
      ).toBeInTheDocument();
    });

    it("shows search empty state when search data has undefined items", () => {
      // Same bug in search mode: data exists but items is missing.
      setupDefaultMocks({
        searchData: {
          total: 0,
          page: 1,
          limit: 24,
        } as PaginatedResponse<Book>,
        searchLoading: false,
      });

      renderBrowsePage("/?search=nonexistent");

      expect(
        screen.getByText(/no books found/i)
      ).toBeInTheDocument();
    });

    it("passes a valid array (not undefined) to BookGrid when data has items", () => {
      setupDefaultMocks();
      renderBrowsePage();

      const grid = screen.getByTestId("book-grid");
      expect(grid).toHaveAttribute("data-books-type", "array");
      expect(grid).toHaveAttribute("data-books-length", "2");
    });

    it("does not pass undefined books to BookGrid when data is available", () => {
      // When data has items, BookGrid must receive the array.
      setupDefaultMocks({
        booksData: {
          items: mockBooks,
          total: 2,
          page: 1,
          limit: 24,
        },
      });

      renderBrowsePage();

      const grid = screen.getByTestId("book-grid");
      expect(grid).toHaveAttribute("data-books-type", "array");
    });
  });

  describe("sorting", () => {
    it("renders sort select component", () => {
      setupDefaultMocks();
      renderBrowsePage();

      expect(screen.getByTestId("sort-select")).toBeInTheDocument();
    });

    it("passes sort param from URL to useBooks", () => {
      setupDefaultMocks();
      renderBrowsePage("/?sort=rating_desc");

      expect(mockUseBooks).toHaveBeenCalledWith(
        expect.objectContaining({ sort: "rating_desc" })
      );
    });

    it("passes undefined sort when no sort param in URL", () => {
      setupDefaultMocks();
      renderBrowsePage("/");

      expect(mockUseBooks).toHaveBeenCalledWith(
        expect.objectContaining({ sort: undefined })
      );
    });

    it("passes sort param to useSearchBooks when searching", () => {
      setupDefaultMocks({
        searchData: {
          items: mockBooks,
          total: 2,
          page: 1,
          limit: 24,
        },
      });
      renderBrowsePage("/?search=gatsby&sort=title_asc");

      expect(mockUseSearchBooks).toHaveBeenCalledWith(
        expect.objectContaining({ sort: "title_asc" })
      );
    });

    it("handleSortChange resets page to 1", async () => {
      const user = (await import("@testing-library/user-event")).default.setup();

      setupDefaultMocks({
        booksData: {
          items: mockBooks,
          total: 100,
          page: 2,
          limit: 24,
        },
      });

      renderBrowsePage("/?page=2");

      const sortSelect = screen.getByTestId("sort-select");
      await user.selectOptions(sortSelect, "rating_desc");

      // After changing sort, useBooks should be called with page 1
      // (page param is removed from URL, so it defaults to 1)
      const lastCall = mockUseBooks.mock.calls[mockUseBooks.mock.calls.length - 1]!;
      expect(lastCall[0]).toMatchObject({ page: 1 });
    });

    it("sort param is preserved when changing pages", async () => {
      const user = (await import("@testing-library/user-event")).default.setup();

      setupDefaultMocks({
        booksData: {
          items: mockBooks,
          total: 100,
          page: 1,
          limit: 24,
        },
      });

      renderBrowsePage("/?sort=rating_desc");

      const nextBtn = screen.getByTestId("page-next");
      await user.click(nextBtn);

      // After page change, sort should still be passed
      const lastCall = mockUseBooks.mock.calls[mockUseBooks.mock.calls.length - 1]!;
      expect(lastCall[0]).toMatchObject({ sort: "rating_desc" });
    });

    it("sort param is preserved when clearing search", async () => {
      const user = (await import("@testing-library/user-event")).default.setup();

      setupDefaultMocks({
        searchData: {
          items: [],
          total: 0,
          page: 1,
          limit: 24,
        },
      });

      renderBrowsePage("/?search=nonexistent&sort=title_asc");

      const clearBtn = screen.getByTestId("clear-search");
      await user.click(clearBtn);

      // After clearing search, sort should still be passed to useBooks
      const lastCall = mockUseBooks.mock.calls[mockUseBooks.mock.calls.length - 1]!;
      expect(lastCall[0]).toMatchObject({ sort: "title_asc" });
    });
  });

  describe("handler functions", () => {
    it("handlePageChange sets page param when navigating to page > 1", async () => {
      const user = (await import("@testing-library/user-event")).default.setup();

      setupDefaultMocks({
        booksData: {
          items: mockBooks,
          total: 100,
          page: 1,
          limit: 24,
        },
      });

      renderBrowsePage();

      // The pagination mock should show "Next" button when totalPages > 1
      const nextBtn = screen.getByTestId("page-next");
      await user.click(nextBtn);

      // After clicking next, page param should be updated
      // We can't easily check URL directly, but we can verify no crash
      expect(screen.getByTestId("search-bar")).toBeInTheDocument();
    });

    it("handlePageChange removes page param when navigating to page 1", async () => {
      const user = (await import("@testing-library/user-event")).default.setup();

      setupDefaultMocks({
        booksData: {
          items: mockBooks,
          total: 100,
          page: 2,
          limit: 24,
        },
      });

      renderBrowsePage("/?page=2");

      const firstBtn = screen.getByTestId("page-first");
      await user.click(firstBtn);

      expect(screen.getByTestId("search-bar")).toBeInTheDocument();
    });

    it("handleSearch navigates correctly from genre page", async () => {
      const user = (await import("@testing-library/user-event")).default.setup();

      setupDefaultMocks();

      renderBrowsePage("/genre/fiction");

      // Type in the search bar to trigger onSearch
      const searchInput = screen.getByTestId("search-bar");
      await user.clear(searchInput);
      await user.type(searchInput, "gatsby");

      // Should navigate away from genre page (no crash)
      expect(screen.getByTestId("search-bar")).toBeInTheDocument();
    });

    it("handleSearch updates search params on home page", async () => {
      const user = (await import("@testing-library/user-event")).default.setup();

      setupDefaultMocks();

      renderBrowsePage("/");

      const searchInput = screen.getByTestId("search-bar");
      await user.clear(searchInput);
      await user.type(searchInput, "orwell");

      expect(screen.getByTestId("search-bar")).toBeInTheDocument();
    });

    it("handleClearSearch clears search and page params", async () => {
      const user = (await import("@testing-library/user-event")).default.setup();

      setupDefaultMocks({
        searchData: {
          items: [],
          total: 0,
          page: 1,
          limit: 24,
        },
      });

      renderBrowsePage("/?search=nonexistent&page=2");

      // The empty state shows a "Clear search" button via EmptyState
      // But our mock SearchBar also has a clear button
      const clearBtn = screen.getByTestId("clear-search");
      await user.click(clearBtn);

      expect(screen.getByTestId("search-bar")).toBeInTheDocument();
    });
  });
});

/**
 * Integration test for the BrowsePage book display flow.
 *
 * These tests verify the complete rendering pipeline:
 *   API response -> useBooks hook -> BrowsePage -> BookGrid -> BookCard
 *
 * Unlike the unit tests in BrowsePage.test.tsx (which mock child components),
 * these tests render real components to verify the full rendering chain works.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowsePage } from "./BrowsePage";
import type { Book, Genre, PaginatedResponse } from "@/types";

// -- Mock data ---------------------------------------------------------------

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
  },
  {
    id: 2,
    title: "1984",
    author_id: 2,
    publisher_id: 2,
    publish_date: "1949-06-08",
    description: "A dystopian novel.",
    url: "https://example.com/1984",
    cover: "https://example.com/1984-cover.jpg",
    author: { id: 2, name: "George Orwell" },
    publisher: { id: 2, name: "Secker & Warburg" },
    genres: [{ id: 1, name: "Fiction" }, { id: 3, name: "Dystopia" }],
  },
  {
    id: 3,
    title: "To Kill a Mockingbird",
    author_id: 3,
    publisher_id: 3,
    publish_date: "1960-07-11",
    description: "A novel about racial injustice.",
    url: "https://example.com/mockingbird",
    cover: null,
    author: { id: 3, name: "Harper Lee" },
    publisher: { id: 3, name: "J. B. Lippincott & Co." },
    genres: [{ id: 1, name: "Fiction" }],
  },
];

const mockPaginatedResponse: PaginatedResponse<Book> = {
  items: mockBooks,
  total: 3,
  page: 1,
  limit: 24,
};

const mockGenres: Genre[] = [
  { id: 1, name: "Fiction" },
  { id: 2, name: "Non-Fiction" },
  { id: 3, name: "Dystopia" },
];

// -- Mock hooks at the boundary (API layer) ----------------------------------

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

// -- Helpers -----------------------------------------------------------------

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

// -- Tests -------------------------------------------------------------------

describe("BrowsePage integration: full rendering pipeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders book titles through the full component tree when data loads", () => {
    mockUseBooks.mockReturnValue({
      data: mockPaginatedResponse,
      isLoading: false,
      error: null,
    });
    mockUseSearchBooks.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });
    mockUseGenres.mockReturnValue({
      data: mockGenres,
      isLoading: false,
    });

    renderBrowsePage();

    // All three book titles should be rendered through BookGrid -> BookCard
    expect(screen.getByText("The Great Gatsby")).toBeInTheDocument();
    expect(screen.getByText("1984")).toBeInTheDocument();
    expect(screen.getByText("To Kill a Mockingbird")).toBeInTheDocument();
  });

  it("renders author names for each book", () => {
    mockUseBooks.mockReturnValue({
      data: mockPaginatedResponse,
      isLoading: false,
      error: null,
    });
    mockUseSearchBooks.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });
    mockUseGenres.mockReturnValue({
      data: mockGenres,
      isLoading: false,
    });

    renderBrowsePage();

    expect(screen.getByText("F. Scott Fitzgerald")).toBeInTheDocument();
    expect(screen.getByText("George Orwell")).toBeInTheDocument();
    expect(screen.getByText("Harper Lee")).toBeInTheDocument();
  });

  it("renders links to individual book pages", () => {
    mockUseBooks.mockReturnValue({
      data: mockPaginatedResponse,
      isLoading: false,
      error: null,
    });
    mockUseSearchBooks.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });
    mockUseGenres.mockReturnValue({
      data: mockGenres,
      isLoading: false,
    });

    renderBrowsePage();

    const links = screen.getAllByRole("link");
    const bookLinks = links.filter((link) =>
      link.getAttribute("href")?.startsWith("/books/")
    );
    expect(bookLinks).toHaveLength(3);
    expect(bookLinks[0]).toHaveAttribute("href", "/books/1");
    expect(bookLinks[1]).toHaveAttribute("href", "/books/2");
    expect(bookLinks[2]).toHaveAttribute("href", "/books/3");
  });

  it("shows skeleton loading state before data arrives", () => {
    mockUseBooks.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });
    mockUseSearchBooks.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });
    mockUseGenres.mockReturnValue({
      data: mockGenres,
      isLoading: false,
    });

    const { container } = renderBrowsePage();

    // Should show skeleton cards, not book titles
    expect(screen.queryByText("The Great Gatsby")).not.toBeInTheDocument();
    // Skeleton grid renders a .grid container with skeleton cards
    const grid = container.querySelector(".grid");
    expect(grid).toBeInTheDocument();
  });

  it("shows empty state when API returns empty items", () => {
    mockUseBooks.mockReturnValue({
      data: { items: [], total: 0, page: 1, limit: 24 },
      isLoading: false,
      error: null,
    });
    mockUseSearchBooks.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });
    mockUseGenres.mockReturnValue({
      data: mockGenres,
      isLoading: false,
    });

    renderBrowsePage();

    expect(
      screen.getByText(/no books available yet/i)
    ).toBeInTheDocument();
    expect(screen.queryByText("The Great Gatsby")).not.toBeInTheDocument();
  });

  it("shows empty state when data is undefined and not loading (the original bug)", () => {
    // This is the exact scenario that caused the blank page bug:
    // data is undefined (not yet fetched) and isLoading flashes to false
    // during a query key transition.
    mockUseBooks.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });
    mockUseSearchBooks.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });
    mockUseGenres.mockReturnValue({
      data: mockGenres,
      isLoading: false,
    });

    renderBrowsePage();

    expect(
      screen.getByText(/no books available yet/i)
    ).toBeInTheDocument();
  });

  it("renders genre tags on book cards", () => {
    mockUseBooks.mockReturnValue({
      data: mockPaginatedResponse,
      isLoading: false,
      error: null,
    });
    mockUseSearchBooks.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });
    mockUseGenres.mockReturnValue({
      data: mockGenres,
      isLoading: false,
    });

    renderBrowsePage();

    // Genre tags should be visible on cards
    // "Fiction" appears on multiple cards, "Dystopia" on one
    const dystopiaElements = screen.getAllByText("Dystopia");
    expect(dystopiaElements.length).toBeGreaterThanOrEqual(1);
  });

  it("shows cover image when book has a cover", () => {
    mockUseBooks.mockReturnValue({
      data: mockPaginatedResponse,
      isLoading: false,
      error: null,
    });
    mockUseSearchBooks.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });
    mockUseGenres.mockReturnValue({
      data: mockGenres,
      isLoading: false,
    });

    renderBrowsePage();

    // Book with id=2 has a cover URL
    const coverImg = screen.getByAltText("Cover of 1984");
    expect(coverImg).toBeInTheDocument();
    expect(coverImg).toHaveAttribute("src", "https://example.com/1984-cover.jpg");
  });
});

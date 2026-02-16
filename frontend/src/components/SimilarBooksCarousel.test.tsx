import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { SimilarBooksCarousel } from "./SimilarBooksCarousel";
import type { Book } from "@/types";

// -- Mock useSimilarBooks hook -----------------------------------------------

const mockUseSimilarBooks = vi.fn();

vi.mock("@/hooks/useSimilarBooks", () => ({
  useSimilarBooks: (...args: unknown[]) => mockUseSimilarBooks(...args),
}));

// -- Test data ---------------------------------------------------------------

const mockBooks: Book[] = [
  {
    id: 10,
    title: "Similar Book One",
    author_id: 1,
    publisher_id: 1,
    publish_date: "2024-03-01",
    description: "A similar book.",
    url: "https://example.com/book/10",
    cover: "https://example.com/cover10.jpg",
    author: { id: 1, name: "Author One" },
    publisher: { id: 1, name: "Publisher One" },
    genres: [],
    avg_critic_rating: 3.8,
    review_count: 5,
  },
  {
    id: 20,
    title: "Similar Book Two",
    author_id: 2,
    publisher_id: 2,
    publish_date: "2024-06-15",
    description: "Another similar book.",
    url: "https://example.com/book/20",
    cover: null,
    author: { id: 2, name: "Author Two" },
    publisher: null,
    genres: [],
    avg_critic_rating: null,
    review_count: 0,
  },
];

// -- Helpers -----------------------------------------------------------------

function renderCarousel(bookId: number = 42, enabled: boolean = true) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SimilarBooksCarousel bookId={bookId} enabled={enabled} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// -- Tests -------------------------------------------------------------------

describe("SimilarBooksCarousel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders section heading and book cards when data is available", () => {
    mockUseSimilarBooks.mockReturnValue({
      data: mockBooks,
      isLoading: false,
      isError: false,
    });

    renderCarousel();

    expect(screen.getByText("Readers Also Enjoyed")).toBeInTheDocument();
    expect(screen.getByText("Similar Book One")).toBeInTheDocument();
    expect(screen.getByText("Similar Book Two")).toBeInTheDocument();
    expect(screen.getByTestId("similar-books-carousel")).toBeInTheDocument();
  });

  it("renders skeleton loading state", () => {
    mockUseSimilarBooks.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    renderCarousel();

    expect(screen.getByTestId("similar-books-skeleton")).toBeInTheDocument();
    expect(screen.getByText("Readers Also Enjoyed")).toBeInTheDocument();
  });

  it("returns null when data is empty", () => {
    mockUseSimilarBooks.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    const { container } = renderCarousel();

    expect(container.innerHTML).toBe("");
  });

  it("returns null when there is an error", () => {
    mockUseSimilarBooks.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    const { container } = renderCarousel();

    expect(container.innerHTML).toBe("");
  });

  it("returns null when data is undefined and not loading", () => {
    mockUseSimilarBooks.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });

    const { container } = renderCarousel();

    expect(container.innerHTML).toBe("");
  });

  it("passes bookId and enabled to the hook", () => {
    mockUseSimilarBooks.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    renderCarousel(99, false);

    expect(mockUseSimilarBooks).toHaveBeenCalledWith(99, false);
  });

  it("renders scroll container with correct test id", () => {
    mockUseSimilarBooks.mockReturnValue({
      data: mockBooks,
      isLoading: false,
      isError: false,
    });

    renderCarousel();

    expect(
      screen.getByTestId("similar-books-scroll-container")
    ).toBeInTheDocument();
  });

  it("renders one CompactBookCard per book", () => {
    mockUseSimilarBooks.mockReturnValue({
      data: mockBooks,
      isLoading: false,
      isError: false,
    });

    renderCarousel();

    const cards = screen.getAllByTestId("compact-book-card");
    expect(cards).toHaveLength(2);
  });
});

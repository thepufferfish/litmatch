import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { BookGrid } from "./BookGrid";
import type { Book } from "@/types";

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
  },
];

// ── Helpers ──────────────────────────────────────────────────────────

function renderBookGrid(props: { books: Book[]; isLoading: boolean }) {
  return render(
    <MemoryRouter>
      <BookGrid {...props} />
    </MemoryRouter>
  );
}

// ── Tests ────────────────────────────────────────────────────────────

describe("BookGrid", () => {
  describe("loading state", () => {
    it("renders skeleton grid when isLoading is true", () => {
      const { container } = renderBookGrid({ books: [], isLoading: true });

      // SkeletonGrid renders a grid div with skeleton cards
      const grid = container.querySelector(".grid");
      expect(grid).toBeInTheDocument();
    });

    it("does not render book cards when loading", () => {
      renderBookGrid({ books: mockBooks, isLoading: true });

      // Should show skeleton, not actual books
      expect(screen.queryByText("The Great Gatsby")).not.toBeInTheDocument();
    });
  });

  describe("with books", () => {
    it("renders all book cards when books array is provided", () => {
      renderBookGrid({ books: mockBooks, isLoading: false });

      expect(screen.getByText("The Great Gatsby")).toBeInTheDocument();
      expect(screen.getByText("1984")).toBeInTheDocument();
    });

    it("renders links to book detail pages", () => {
      renderBookGrid({ books: mockBooks, isLoading: false });

      const links = screen.getAllByRole("link");
      expect(links).toHaveLength(2);
      expect(links[0]).toHaveAttribute("href", "/books/1");
      expect(links[1]).toHaveAttribute("href", "/books/2");
    });
  });

  describe("empty books array", () => {
    it("returns null when books is an empty array", () => {
      // Empty array returns null from BookGrid.
      // The empty state message is BrowsePage's responsibility.
      const { container } = renderBookGrid({
        books: [],
        isLoading: false,
      });

      expect(container.innerHTML).toBe("");
    });
  });
});

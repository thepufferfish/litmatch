import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { CompactBookCard } from "./CompactBookCard";
import type { Book } from "@/types";

const baseBook: Book = {
  id: 1,
  title: "Test Book",
  author_id: 1,
  publisher_id: 1,
  publish_date: "2024-01-01",
  description: "A test book.",
  url: "https://example.com",
  cover: "https://example.com/cover.jpg",
  author: { id: 1, name: "Test Author" },
  publisher: { id: 1, name: "Test Publisher" },
  genres: [{ id: 1, name: "Fiction" }],
  avg_critic_rating: 3.5,
  review_count: 10,
};

function renderCompactBookCard(book: Book) {
  return render(
    <MemoryRouter>
      <CompactBookCard book={book} />
    </MemoryRouter>
  );
}

describe("CompactBookCard", () => {
  it("renders book title", () => {
    renderCompactBookCard(baseBook);
    expect(screen.getByText("Test Book")).toBeInTheDocument();
  });

  it("renders author name", () => {
    renderCompactBookCard(baseBook);
    expect(screen.getByText("Test Author")).toBeInTheDocument();
  });

  it("renders 'Unknown Author' when author is null", () => {
    renderCompactBookCard({ ...baseBook, author: null, author_id: null });
    expect(screen.getByText("Unknown Author")).toBeInTheDocument();
  });

  it("renders cover image with lazy loading", () => {
    renderCompactBookCard(baseBook);
    const img = screen.getByAltText("Cover of Test Book");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("loading", "lazy");
  });

  it("renders book icon placeholder when cover is null", () => {
    renderCompactBookCard({ ...baseBook, cover: null });
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    const svg = document.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("renders critic rating badge when avg_critic_rating exists", () => {
    renderCompactBookCard(baseBook);
    expect(screen.getByTestId("critic-rating-badge")).toBeInTheDocument();
  });

  it("does not render critic rating badge when avg_critic_rating is null", () => {
    renderCompactBookCard({ ...baseBook, avg_critic_rating: null });
    expect(screen.queryByTestId("critic-rating-badge")).not.toBeInTheDocument();
  });

  it("links to the book detail page", () => {
    renderCompactBookCard(baseBook);
    const link = screen.getByTestId("compact-book-card");
    expect(link).toHaveAttribute("href", "/books/1");
  });

  it("does not render description or genres", () => {
    renderCompactBookCard(baseBook);
    expect(screen.queryByText("A test book.")).not.toBeInTheDocument();
    expect(screen.queryByText("Fiction")).not.toBeInTheDocument();
  });

  it("does not show review count (no showCount prop)", () => {
    renderCompactBookCard(baseBook);
    expect(screen.queryByText(/from.*reviews/)).not.toBeInTheDocument();
  });
});

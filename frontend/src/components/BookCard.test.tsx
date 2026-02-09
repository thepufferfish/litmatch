import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { BookCard } from "./BookCard";
import type { Book } from "@/types";

const baseBook: Book = {
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
  genres: [],
  avg_critic_rating: 3.5,
  review_count: 10,
};

function renderBookCard(book: Book) {
  return render(
    <MemoryRouter>
      <BookCard book={book} />
    </MemoryRouter>
  );
}

describe("BookCard", () => {
  it("displays review count next to critic rating", () => {
    renderBookCard(baseBook);
    expect(screen.getByText("from 10 reviews")).toBeInTheDocument();
  });

  it("displays singular 'review' for count of 1", () => {
    renderBookCard({ ...baseBook, review_count: 1 });
    expect(screen.getByText("from 1 review")).toBeInTheDocument();
  });

  it("does not display critic badge when avg_critic_rating is null", () => {
    renderBookCard({ ...baseBook, avg_critic_rating: null, review_count: 0 });
    expect(screen.queryByTestId("critic-rating-badge")).not.toBeInTheDocument();
  });

  it("does not display review count text when review_count is 0", () => {
    renderBookCard({ ...baseBook, review_count: 0 });
    expect(screen.queryByText(/from 0/)).not.toBeInTheDocument();
  });
});

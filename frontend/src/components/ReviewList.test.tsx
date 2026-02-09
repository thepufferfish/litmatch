import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewList } from "./ReviewList";
import type { Review } from "@/types";

// -- Mock data ---------------------------------------------------------------

function createReview(overrides: Partial<Review> = {}): Review {
  return {
    id: 1,
    book_id: 42,
    rating: 3,
    review: "A thoughtful exploration of modern themes.",
    url: "https://example.com/review/1",
    critic: { id: 1, name: "Jane Critic" },
    publication: { id: 1, name: "The Literary Review" },
    ...overrides,
  };
}

function createReviews(count: number): Review[] {
  return Array.from({ length: count }, (_, i) =>
    createReview({
      id: i + 1,
      rating: ((i % 4) + 1) as 1 | 2 | 3 | 4,
      review: `Review text for book ${i + 1}.`,
      critic: { id: i + 1, name: `Critic ${i + 1}` },
      publication: { id: i + 1, name: `Publication ${i + 1}` },
    })
  );
}

// -- Tests -------------------------------------------------------------------

describe("ReviewList", () => {
  describe("empty state", () => {
    it("shows a message when reviews array is empty", () => {
      render(<ReviewList reviews={[]} />);

      expect(
        screen.getByText(/no critic reviews available/i)
      ).toBeInTheDocument();
    });
  });

  describe("rendering reviews", () => {
    it("renders a single review with critic name and publication", () => {
      const review = createReview();
      render(<ReviewList reviews={[review]} />);

      expect(screen.getByText("Jane Critic")).toBeInTheDocument();
      expect(screen.getByText(/The Literary Review/)).toBeInTheDocument();
      expect(
        screen.getByText(/thoughtful exploration/i)
      ).toBeInTheDocument();
    });

    it("renders 'Anonymous' when critic is null", () => {
      const review = createReview({ critic: null });
      render(<ReviewList reviews={[review]} />);

      expect(screen.getByText("Anonymous")).toBeInTheDocument();
    });

    it("does not render publication when it is null", () => {
      const review = createReview({ publication: null });
      render(<ReviewList reviews={[review]} />);

      expect(screen.getByText("Jane Critic")).toBeInTheDocument();
      // Publication dash separator should not be present
      expect(screen.queryByText(/Literary Review/)).not.toBeInTheDocument();
    });

    it("does not render review text when review string is empty", () => {
      const review = createReview({ review: "" });
      render(<ReviewList reviews={[review]} />);

      // Should render the critic but not a paragraph with review text
      expect(screen.getByText("Jane Critic")).toBeInTheDocument();
      expect(
        screen.queryByText(/thoughtful exploration/i)
      ).not.toBeInTheDocument();
    });
  });

  describe("rating labels", () => {
    it("shows 'Rave' label for rating 4", () => {
      const review = createReview({ rating: 4 });
      render(<ReviewList reviews={[review]} />);

      expect(screen.getByText("Rave")).toBeInTheDocument();
    });

    it("shows 'Positive' label for rating 3", () => {
      const review = createReview({ rating: 3 });
      render(<ReviewList reviews={[review]} />);

      expect(screen.getByText("Positive")).toBeInTheDocument();
    });

    it("shows 'Mixed' label for rating 2", () => {
      const review = createReview({ rating: 2 });
      render(<ReviewList reviews={[review]} />);

      expect(screen.getByText("Mixed")).toBeInTheDocument();
    });

    it("shows 'Pan' label for rating 1", () => {
      const review = createReview({ rating: 1 });
      render(<ReviewList reviews={[review]} />);

      expect(screen.getByText("Pan")).toBeInTheDocument();
    });

    it("shows 'Unknown' label for unexpected rating value", () => {
      const review = createReview({ rating: 0 });
      render(<ReviewList reviews={[review]} />);

      expect(screen.getByText("Unknown")).toBeInTheDocument();
    });

    it("shows 'Unknown' label for rating 5 (out of expected range)", () => {
      const review = createReview({ rating: 5 });
      render(<ReviewList reviews={[review]} />);

      expect(screen.getByText("Unknown")).toBeInTheDocument();
    });
  });

  describe("expand/collapse with more than 5 reviews", () => {
    it("shows only first 5 reviews initially", () => {
      const reviews = createReviews(8);
      render(<ReviewList reviews={reviews} />);

      // Should see critics 1-5 but not 6-8
      for (let i = 1; i <= 5; i++) {
        expect(screen.getByText(`Critic ${i}`)).toBeInTheDocument();
      }
      expect(screen.queryByText("Critic 6")).not.toBeInTheDocument();
      expect(screen.queryByText("Critic 7")).not.toBeInTheDocument();
      expect(screen.queryByText("Critic 8")).not.toBeInTheDocument();
    });

    it("shows 'Show all N reviews' button when there are more than 5", () => {
      const reviews = createReviews(8);
      render(<ReviewList reviews={reviews} />);

      expect(
        screen.getByText("Show all 8 reviews")
      ).toBeInTheDocument();
    });

    it("does not show expand button when there are 5 or fewer reviews", () => {
      const reviews = createReviews(5);
      render(<ReviewList reviews={reviews} />);

      expect(
        screen.queryByText(/show all/i)
      ).not.toBeInTheDocument();
    });

    it("shows all reviews after clicking expand button", async () => {
      const user = userEvent.setup();
      const reviews = createReviews(8);
      render(<ReviewList reviews={reviews} />);

      await user.click(screen.getByText("Show all 8 reviews"));

      // All 8 critics should now be visible
      for (let i = 1; i <= 8; i++) {
        expect(screen.getByText(`Critic ${i}`)).toBeInTheDocument();
      }
    });

    it("hides the expand button after expanding", async () => {
      const user = userEvent.setup();
      const reviews = createReviews(8);
      render(<ReviewList reviews={reviews} />);

      await user.click(screen.getByText("Show all 8 reviews"));

      expect(
        screen.queryByText(/show all/i)
      ).not.toBeInTheDocument();
    });
  });

  describe("exactly 5 reviews (boundary)", () => {
    it("shows all 5 reviews without expand button", () => {
      const reviews = createReviews(5);
      render(<ReviewList reviews={reviews} />);

      for (let i = 1; i <= 5; i++) {
        expect(screen.getByText(`Critic ${i}`)).toBeInTheDocument();
      }
      expect(screen.queryByText(/show all/i)).not.toBeInTheDocument();
    });
  });

  describe("exactly 6 reviews (boundary + 1)", () => {
    it("shows first 5 reviews with expand button", () => {
      const reviews = createReviews(6);
      render(<ReviewList reviews={reviews} />);

      for (let i = 1; i <= 5; i++) {
        expect(screen.getByText(`Critic ${i}`)).toBeInTheDocument();
      }
      expect(screen.queryByText("Critic 6")).not.toBeInTheDocument();
      expect(screen.getByText("Show all 6 reviews")).toBeInTheDocument();
    });
  });
});

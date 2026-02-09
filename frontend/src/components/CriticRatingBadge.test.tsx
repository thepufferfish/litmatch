import { render, screen } from "@testing-library/react";
import { CriticRatingBadge } from "./CriticRatingBadge";

describe("CriticRatingBadge", () => {
  it("renders nothing when avgRating is null", () => {
    const { container } = render(
      <CriticRatingBadge avgRating={null} reviewCount={0} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders Rave label for avg >= 3.5", () => {
    render(<CriticRatingBadge avgRating={3.7} reviewCount={5} />);
    expect(screen.getByText(/3\.7/)).toBeInTheDocument();
    expect(screen.getByText(/Rave/)).toBeInTheDocument();
  });

  it("renders Positive label for avg >= 2.5 and < 3.5", () => {
    render(<CriticRatingBadge avgRating={3.0} reviewCount={3} />);
    expect(screen.getByText(/3\.0/)).toBeInTheDocument();
    expect(screen.getByText(/Positive/)).toBeInTheDocument();
  });

  it("renders Mixed label for avg >= 1.5 and < 2.5", () => {
    render(<CriticRatingBadge avgRating={2.0} reviewCount={2} />);
    expect(screen.getByText(/2\.0/)).toBeInTheDocument();
    expect(screen.getByText(/Mixed/)).toBeInTheDocument();
  });

  it("renders Pan label for avg < 1.5", () => {
    render(<CriticRatingBadge avgRating={1.2} reviewCount={1} />);
    expect(screen.getByText(/1\.2/)).toBeInTheDocument();
    expect(screen.getByText(/Pan/)).toBeInTheDocument();
  });

  it("renders Rave at exactly 3.5", () => {
    render(<CriticRatingBadge avgRating={3.5} reviewCount={4} />);
    expect(screen.getByText(/Rave/)).toBeInTheDocument();
  });

  it("renders Positive at exactly 2.5", () => {
    render(<CriticRatingBadge avgRating={2.5} reviewCount={4} />);
    expect(screen.getByText(/Positive/)).toBeInTheDocument();
  });

  it("renders Mixed at exactly 1.5", () => {
    render(<CriticRatingBadge avgRating={1.5} reviewCount={4} />);
    expect(screen.getByText(/Mixed/)).toBeInTheDocument();
  });

  it("does not show review count by default", () => {
    render(<CriticRatingBadge avgRating={3.0} reviewCount={5} />);
    expect(screen.queryByText(/reviews/)).not.toBeInTheDocument();
  });

  it("shows review count when showCount is true", () => {
    render(
      <CriticRatingBadge avgRating={3.0} reviewCount={12} showCount />
    );
    expect(screen.getByText("from 12 reviews")).toBeInTheDocument();
  });

  it("shows singular 'review' for count of 1", () => {
    render(
      <CriticRatingBadge avgRating={4.0} reviewCount={1} showCount />
    );
    expect(screen.getByText("from 1 review")).toBeInTheDocument();
  });

  it("has correct test id for querying", () => {
    render(<CriticRatingBadge avgRating={3.0} reviewCount={5} />);
    expect(screen.getByTestId("critic-rating-badge")).toBeInTheDocument();
  });

  it("uses rave color classes for high ratings", () => {
    render(<CriticRatingBadge avgRating={3.8} reviewCount={5} />);
    const badge = screen.getByTestId("critic-rating-badge");
    const span = badge.querySelector("span");
    expect(span?.className).toContain("bg-rave-bg");
    expect(span?.className).toContain("text-rave");
  });

  it("uses positive color classes for positive ratings", () => {
    render(<CriticRatingBadge avgRating={3.0} reviewCount={5} />);
    const badge = screen.getByTestId("critic-rating-badge");
    const span = badge.querySelector("span");
    expect(span?.className).toContain("bg-positive-bg");
    expect(span?.className).toContain("text-positive");
  });

  it("uses mixed color classes for mixed ratings", () => {
    render(<CriticRatingBadge avgRating={2.0} reviewCount={5} />);
    const badge = screen.getByTestId("critic-rating-badge");
    const span = badge.querySelector("span");
    expect(span?.className).toContain("bg-mixed-bg");
    expect(span?.className).toContain("text-mixed");
  });

  it("uses pan color classes for low ratings", () => {
    render(<CriticRatingBadge avgRating={1.0} reviewCount={5} />);
    const badge = screen.getByTestId("critic-rating-badge");
    const span = badge.querySelector("span");
    expect(span?.className).toContain("bg-pan-bg");
    expect(span?.className).toContain("text-pan");
  });
});

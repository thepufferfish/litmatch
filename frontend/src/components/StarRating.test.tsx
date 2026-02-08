import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StarRating } from "./StarRating";

describe("StarRating", () => {
  it("renders 5 star buttons", () => {
    render(<StarRating value={0} />);
    const stars = screen.getAllByRole("img", { hidden: true });
    expect(stars).toHaveLength(5);
  });

  it("displays filled stars up to the value", () => {
    render(<StarRating value={3} />);
    const stars = screen.getAllByTestId(/^star-/);
    expect(stars[0]).toHaveAttribute("data-filled", "true");
    expect(stars[1]).toHaveAttribute("data-filled", "true");
    expect(stars[2]).toHaveAttribute("data-filled", "true");
    expect(stars[3]).toHaveAttribute("data-filled", "false");
    expect(stars[4]).toHaveAttribute("data-filled", "false");
  });

  it("calls onChange when a star is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<StarRating value={0} onChange={onChange} />);

    const stars = screen.getAllByTestId(/^star-/);
    await user.click(stars[2]!);
    expect(onChange).toHaveBeenCalledWith(3);
  });

  it("does not call onChange when disabled", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<StarRating value={0} onChange={onChange} disabled />);

    const stars = screen.getAllByTestId(/^star-/);
    await user.click(stars[2]!);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("renders as read-only when onChange is not provided", () => {
    render(<StarRating value={4} />);
    // No click handler so buttons should not exist
    const buttons = screen.queryAllByRole("button");
    expect(buttons).toHaveLength(0);
  });

  it("renders as interactive buttons when onChange is provided", () => {
    render(<StarRating value={2} onChange={vi.fn()} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(5);
  });

  it("displays correct aria-label for each star", () => {
    render(<StarRating value={0} onChange={vi.fn()} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons[0]).toHaveAttribute("aria-label", "Rate 1 star");
    expect(buttons[4]).toHaveAttribute("aria-label", "Rate 5 stars");
  });
});

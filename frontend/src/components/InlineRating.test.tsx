import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { InlineRating } from "./InlineRating";

function renderInlineRating(props: {
  bookId: number;
  userRating?: number;
  onRate?: (bookId: number, rating: number | null) => void;
  isDisabled?: boolean;
  isAuthenticated: boolean;
}) {
  return render(
    <MemoryRouter>
      <InlineRating
        bookId={props.bookId}
        userRating={props.userRating}
        onRate={props.onRate}
        isDisabled={props.isDisabled}
        isAuthenticated={props.isAuthenticated}
      />
    </MemoryRouter>
  );
}

describe("InlineRating", () => {
  it("shows 'Log in to rate' when not authenticated", () => {
    renderInlineRating({ bookId: 1, isAuthenticated: false });

    const link = screen.getByText("Log in to rate");
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("role", "link");
  });

  it("shows interactive stars when authenticated", () => {
    renderInlineRating({
      bookId: 1,
      isAuthenticated: true,
      onRate: vi.fn(),
    });

    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(5);
  });

  it("displays existing rating value", () => {
    renderInlineRating({
      bookId: 1,
      userRating: 3,
      isAuthenticated: true,
      onRate: vi.fn(),
    });

    // Stars 1-3 should be filled
    for (let i = 1; i <= 3; i++) {
      expect(screen.getByTestId(`star-${i}`)).toHaveAttribute("data-filled", "true");
    }
    expect(screen.getByTestId("star-4")).toHaveAttribute("data-filled", "false");
  });

  it("calls onRate with correct bookId and rating", async () => {
    const user = userEvent.setup();
    const onRate = vi.fn();

    renderInlineRating({
      bookId: 42,
      isAuthenticated: true,
      onRate,
    });

    const star4 = screen.getByRole("button", { name: /rate 4 star/i });
    await user.click(star4);

    expect(onRate).toHaveBeenCalledWith(42, 4);
  });

  it("stops event propagation on click", () => {
    const parentClick = vi.fn();

    render(
      <MemoryRouter>
        <div onClick={parentClick}>
          <InlineRating bookId={1} userRating={undefined} isAuthenticated={true} onRate={vi.fn()} />
        </div>
      </MemoryRouter>
    );

    const ratingArea = screen.getByRole("group", { name: /star rating/i }).parentElement!;
    ratingArea.click();

    expect(parentClick).not.toHaveBeenCalled();
  });

  it("renders with disabled state", () => {
    renderInlineRating({
      bookId: 1,
      isAuthenticated: true,
      isDisabled: true,
      onRate: vi.fn(),
    });

    // When disabled, stars render as spans (non-interactive)
    const buttons = screen.queryAllByRole("button");
    expect(buttons).toHaveLength(0);
  });

  it("renders stars with sm size", () => {
    renderInlineRating({
      bookId: 1,
      isAuthenticated: true,
      onRate: vi.fn(),
    });

    // InlineRating always uses size="sm" for compact cards
    const svgs = screen.getAllByRole("img", { hidden: true });
    for (const svg of svgs) {
      expect(svg.classList.contains("w-4")).toBe(true);
      expect(svg.classList.contains("h-4")).toBe(true);
    }
  });

  it("calls onRate with null when user clicks the selected star (unrate)", async () => {
    const user = userEvent.setup();
    const onRate = vi.fn();

    renderInlineRating({
      bookId: 42,
      userRating: 3,
      isAuthenticated: true,
      onRate,
    });

    const star3 = screen.getByRole("button", { name: /clear rating/i });
    await user.click(star3);

    expect(onRate).toHaveBeenCalledWith(42, null);
  });
});

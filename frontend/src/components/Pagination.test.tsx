import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Pagination } from "./Pagination";

describe("Pagination", () => {
  const onPageChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("NaN guard (Bug: zero-length-error)", () => {
    it("returns null when totalPages is NaN", () => {
      const { container } = render(
        <Pagination
          currentPage={1}
          totalPages={NaN}
          onPageChange={onPageChange}
        />
      );

      // NaN <= 1 evaluates to false, so without a fix, the component
      // would try to render NaN as a child element.
      // With the fix, it should return null (render nothing).
      expect(container.innerHTML).toBe("");
    });

    it("returns null when totalPages is Infinity", () => {
      const { container } = render(
        <Pagination
          currentPage={1}
          totalPages={Infinity}
          onPageChange={onPageChange}
        />
      );

      expect(container.innerHTML).toBe("");
    });

    it("returns null when totalPages is negative Infinity", () => {
      const { container } = render(
        <Pagination
          currentPage={1}
          totalPages={-Infinity}
          onPageChange={onPageChange}
        />
      );

      expect(container.innerHTML).toBe("");
    });

    it("returns null when totalPages is 0", () => {
      const { container } = render(
        <Pagination
          currentPage={1}
          totalPages={0}
          onPageChange={onPageChange}
        />
      );

      expect(container.innerHTML).toBe("");
    });

    it("returns null when totalPages is negative", () => {
      const { container } = render(
        <Pagination
          currentPage={1}
          totalPages={-5}
          onPageChange={onPageChange}
        />
      );

      expect(container.innerHTML).toBe("");
    });
  });

  describe("normal rendering", () => {
    it("returns null when totalPages is 1 (single page)", () => {
      const { container } = render(
        <Pagination
          currentPage={1}
          totalPages={1}
          onPageChange={onPageChange}
        />
      );

      expect(container.innerHTML).toBe("");
    });

    it("renders pagination when totalPages is greater than 1", () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={5}
          onPageChange={onPageChange}
        />
      );

      expect(screen.getByRole("navigation")).toBeInTheDocument();
      expect(screen.getByLabelText("Previous page")).toBeInTheDocument();
      expect(screen.getByLabelText("Next page")).toBeInTheDocument();
    });

    it("disables Previous button on first page", () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={5}
          onPageChange={onPageChange}
        />
      );

      expect(screen.getByLabelText("Previous page")).toBeDisabled();
    });

    it("disables Next button on last page", () => {
      render(
        <Pagination
          currentPage={5}
          totalPages={5}
          onPageChange={onPageChange}
        />
      );

      expect(screen.getByLabelText("Next page")).toBeDisabled();
    });

    it("highlights current page with aria-current", () => {
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={onPageChange}
        />
      );

      const currentButton = screen.getByRole("button", { name: "3" });
      expect(currentButton).toHaveAttribute("aria-current", "page");
    });

    it("calls onPageChange when clicking Next", async () => {
      const user = userEvent.setup();

      render(
        <Pagination
          currentPage={2}
          totalPages={5}
          onPageChange={onPageChange}
        />
      );

      await user.click(screen.getByLabelText("Next page"));
      expect(onPageChange).toHaveBeenCalledWith(3);
    });

    it("calls onPageChange when clicking Previous", async () => {
      const user = userEvent.setup();

      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={onPageChange}
        />
      );

      await user.click(screen.getByLabelText("Previous page"));
      expect(onPageChange).toHaveBeenCalledWith(2);
    });

    it("calls onPageChange when clicking a page number", async () => {
      const user = userEvent.setup();

      render(
        <Pagination
          currentPage={1}
          totalPages={5}
          onPageChange={onPageChange}
        />
      );

      await user.click(screen.getByRole("button", { name: "4" }));
      expect(onPageChange).toHaveBeenCalledWith(4);
    });
  });

  describe("buildPageNumbers (via rendered output)", () => {
    it("renders all pages when total is 7 or fewer", () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={7}
          onPageChange={onPageChange}
        />
      );

      for (let i = 1; i <= 7; i++) {
        expect(screen.getByRole("button", { name: String(i) })).toBeInTheDocument();
      }
    });

    it("renders ellipsis for large page counts", () => {
      render(
        <Pagination
          currentPage={5}
          totalPages={20}
          onPageChange={onPageChange}
        />
      );

      // Should always show first and last page
      expect(screen.getByRole("button", { name: "1" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "20" })).toBeInTheDocument();

      // Should show ellipsis
      const ellipses = screen.getAllByText("...");
      expect(ellipses.length).toBeGreaterThanOrEqual(1);
    });
  });
});

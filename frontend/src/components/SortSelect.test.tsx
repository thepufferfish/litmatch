import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SortSelect, SORT_OPTIONS } from "./SortSelect";
import type { BookSortOption } from "@/types";

describe("SortSelect", () => {
  const mockOnChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all sort options plus default", () => {
    render(<SortSelect value={undefined} onChange={mockOnChange} />);

    const select = screen.getByTestId("sort-select") as HTMLSelectElement;
    const options = select.querySelectorAll("option");

    // Default + all sort options
    expect(options).toHaveLength(SORT_OPTIONS.length + 1);
    expect(options[0]!.textContent).toBe("Default");
  });

  it("shows the correct selected value", () => {
    render(<SortSelect value="rating_desc" onChange={mockOnChange} />);

    const select = screen.getByTestId("sort-select") as HTMLSelectElement;
    expect(select.value).toBe("rating_desc");
  });

  it("shows default when value is undefined", () => {
    render(<SortSelect value={undefined} onChange={mockOnChange} />);

    const select = screen.getByTestId("sort-select") as HTMLSelectElement;
    expect(select.value).toBe("");
  });

  it("calls onChange with the selected sort option", async () => {
    const user = userEvent.setup();
    render(<SortSelect value={undefined} onChange={mockOnChange} />);

    const select = screen.getByTestId("sort-select");
    await user.selectOptions(select, "title_asc");

    expect(mockOnChange).toHaveBeenCalledWith("title_asc" as BookSortOption);
  });

  it("calls onChange with undefined when default is selected", async () => {
    const user = userEvent.setup();
    render(<SortSelect value="rating_desc" onChange={mockOnChange} />);

    const select = screen.getByTestId("sort-select");
    await user.selectOptions(select, "");

    expect(mockOnChange).toHaveBeenCalledWith(undefined);
  });

  it("renders a label", () => {
    render(<SortSelect value={undefined} onChange={mockOnChange} />);

    expect(screen.getByText("Sort by")).toBeInTheDocument();
  });
});

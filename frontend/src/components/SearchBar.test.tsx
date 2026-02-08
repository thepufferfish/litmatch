import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SearchBar } from "./SearchBar";

describe("SearchBar", () => {
  it("renders with initial value", () => {
    render(
      <SearchBar initialValue="test" onSearch={vi.fn()} onClear={vi.fn()} />
    );
    expect(screen.getByPlaceholderText(/search/i)).toHaveValue("test");
  });

  it("syncs value when initialValue prop changes", () => {
    const { rerender } = render(
      <SearchBar initialValue="first" onSearch={vi.fn()} onClear={vi.fn()} />
    );

    expect(screen.getByPlaceholderText(/search/i)).toHaveValue("first");

    rerender(
      <SearchBar initialValue="second" onSearch={vi.fn()} onClear={vi.fn()} />
    );

    expect(screen.getByPlaceholderText(/search/i)).toHaveValue("second");
  });

  it("syncs to empty string when initialValue is cleared", () => {
    const { rerender } = render(
      <SearchBar initialValue="query" onSearch={vi.fn()} onClear={vi.fn()} />
    );

    rerender(
      <SearchBar initialValue="" onSearch={vi.fn()} onClear={vi.fn()} />
    );

    expect(screen.getByPlaceholderText(/search/i)).toHaveValue("");
  });

  it("allows user to type independently of initialValue", async () => {
    const user = userEvent.setup();
    render(
      <SearchBar initialValue="" onSearch={vi.fn()} onClear={vi.fn()} />
    );

    const input = screen.getByPlaceholderText(/search/i);
    await user.type(input, "hello");
    expect(input).toHaveValue("hello");
  });

  it("calls onSearch with trimmed value on submit", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(
      <SearchBar initialValue="" onSearch={onSearch} onClear={vi.fn()} />
    );

    const input = screen.getByPlaceholderText(/search/i);
    await user.type(input, "test query");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(onSearch).toHaveBeenCalledWith("test query");
  });

  it("does not call onSearch when query is shorter than 2 chars", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(
      <SearchBar initialValue="" onSearch={onSearch} onClear={vi.fn()} />
    );

    const input = screen.getByPlaceholderText(/search/i);
    await user.type(input, "a{Enter}");

    expect(onSearch).not.toHaveBeenCalled();
  });
});

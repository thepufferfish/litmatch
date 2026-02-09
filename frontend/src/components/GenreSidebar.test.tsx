import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { GenreSidebar } from "./GenreSidebar";
import type { Genre } from "@/types";

// -- Mock useGenres hook -----------------------------------------------------

const mockUseGenres = vi.fn();

vi.mock("@/hooks/useGenres", () => ({
  useGenres: () => mockUseGenres(),
}));

// -- Test data ---------------------------------------------------------------

const mockGenres: Genre[] = [
  { id: 1, name: "Fiction" },
  { id: 2, name: "Non-Fiction" },
  { id: 3, name: "Biography" },
];

// -- Helpers -----------------------------------------------------------------

function renderSidebar(activeGenreSlug?: string) {
  return render(
    <MemoryRouter>
      <GenreSidebar activeGenreSlug={activeGenreSlug} />
    </MemoryRouter>
  );
}

// -- Tests -------------------------------------------------------------------

describe("GenreSidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("loading state", () => {
    it("shows skeleton elements while genres are loading", () => {
      mockUseGenres.mockReturnValue({
        data: undefined,
        isLoading: true,
      });

      const { container } = renderSidebar();

      // Should render skeleton shimmer elements
      const skeletons = container.querySelectorAll(".skeleton-shimmer");
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe("empty state", () => {
    it("renders nothing when genres array is empty", () => {
      mockUseGenres.mockReturnValue({
        data: [],
        isLoading: false,
      });

      const { container } = renderSidebar();

      expect(container.innerHTML).toBe("");
    });

    it("renders nothing when genres is undefined", () => {
      mockUseGenres.mockReturnValue({
        data: undefined,
        isLoading: false,
      });

      const { container } = renderSidebar();

      expect(container.innerHTML).toBe("");
    });
  });

  describe("with genres data", () => {
    beforeEach(() => {
      mockUseGenres.mockReturnValue({
        data: mockGenres,
        isLoading: false,
      });
    });

    it("renders 'All Books' link", () => {
      renderSidebar();

      expect(screen.getByText("All Books")).toBeInTheDocument();
    });

    it("renders genre names sorted alphabetically", () => {
      renderSidebar();

      // Should find all three genre names
      expect(screen.getAllByText("Biography").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Fiction").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Non-Fiction").length).toBeGreaterThanOrEqual(1);
    });

    it("renders links to genre pages with slugified URLs", () => {
      renderSidebar();

      const links = screen.getAllByRole("link");
      const genreLinks = links.filter((link) =>
        link.getAttribute("href")?.startsWith("/genre/")
      );

      // Should have links for all 3 genres
      expect(genreLinks.length).toBeGreaterThanOrEqual(3);

      // Verify slugified URLs exist
      const hrefs = genreLinks.map((l) => l.getAttribute("href"));
      expect(hrefs).toContain("/genre/fiction");
      expect(hrefs).toContain("/genre/non-fiction");
      expect(hrefs).toContain("/genre/biography");
    });

    it("highlights the active genre", () => {
      renderSidebar("fiction");

      // The "All Books" link in the desktop sidebar should not be highlighted
      // The "Fiction" link should be highlighted
      // We check for the active class pattern (bg-leather text-white)
      const allFictionLinks = screen.getAllByText("Fiction");
      // At least one should have the active styling
      const hasActive = allFictionLinks.some((el) => {
        const link = el.closest("a");
        return link?.className.includes("bg-leather");
      });
      expect(hasActive).toBe(true);
    });

    it("highlights 'All Books' when no genre is active", () => {
      renderSidebar();

      const allBooksLink = screen.getByText("All Books").closest("a");
      expect(allBooksLink?.className).toContain("bg-leather");
    });

    it("renders the mobile dropdown select", () => {
      renderSidebar();

      // Should have the select with "All Genres" option
      const select = screen.getByRole("combobox");
      expect(select).toBeInTheDocument();

      const options = screen.getAllByRole("option");
      expect(options[0]).toHaveTextContent("All Genres");
    });

    it("mobile select shows genre options", () => {
      renderSidebar();

      const options = screen.getAllByRole("option");
      // "All Genres" + 3 genre options
      expect(options).toHaveLength(4);
    });
  });

  describe("mobile genre select navigation", () => {
    it("renders the active genre slug as the selected option", () => {
      mockUseGenres.mockReturnValue({
        data: mockGenres,
        isLoading: false,
      });

      renderSidebar("fiction");

      const select = screen.getByRole("combobox");
      expect(select).toHaveValue("fiction");
    });

    it("defaults to empty string (All Genres) when no genre is active", () => {
      mockUseGenres.mockReturnValue({
        data: mockGenres,
        isLoading: false,
      });

      renderSidebar();

      const select = screen.getByRole("combobox");
      expect(select).toHaveValue("");
    });
  });
});

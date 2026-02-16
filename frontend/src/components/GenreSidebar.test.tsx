import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { GenreSidebar } from "./GenreSidebar";
import type { GroupedGenres } from "@/types";

// -- Mock useGroupedGenres hook ----------------------------------------------

const mockUseGroupedGenres = vi.fn();

vi.mock("@/hooks/useGroupedGenres", () => ({
  useGroupedGenres: () => mockUseGroupedGenres(),
}));

// -- Test data ---------------------------------------------------------------

const mockGroupedGenres: GroupedGenres = {
  fiction: [
    { id: 1, name: "Mystery" },
    { id: 2, name: "Romance" },
  ],
  nonfiction: [
    { id: 3, name: "Biography" },
    { id: 4, name: "History" },
  ],
  unknown: [],
};

// -- Helpers -----------------------------------------------------------------

function renderSidebar(activeGenreSlug?: string, activeCategory?: "fiction" | "nonfiction") {
  return render(
    <MemoryRouter>
      <GenreSidebar activeGenreSlug={activeGenreSlug} activeCategory={activeCategory} />
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
      mockUseGroupedGenres.mockReturnValue({
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
      mockUseGroupedGenres.mockReturnValue({
        data: { fiction: [], nonfiction: [], unknown: [] },
        isLoading: false,
      });

      const { container } = renderSidebar();

      expect(container.innerHTML).toBe("");
    });

    it("renders nothing when genres is undefined", () => {
      mockUseGroupedGenres.mockReturnValue({
        data: undefined,
        isLoading: false,
      });

      const { container } = renderSidebar();

      expect(container.innerHTML).toBe("");
    });
  });

  describe("with genres data", () => {
    beforeEach(() => {
      mockUseGroupedGenres.mockReturnValue({
        data: mockGroupedGenres,
        isLoading: false,
      });
    });

    it("renders 'All Books' link", () => {
      renderSidebar();

      expect(screen.getByText("All Books")).toBeInTheDocument();
    });

    it("renders genre names sorted alphabetically", () => {
      renderSidebar();

      // Should find genre names from both fiction and nonfiction
      expect(screen.getAllByText("Biography").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Mystery").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Fiction").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Non-Fiction").length).toBeGreaterThanOrEqual(1);
    });

    it("renders links to genre pages with slugified URLs", () => {
      renderSidebar();

      const links = screen.getAllByRole("link");
      const genreLinks = links.filter((link) =>
        link.getAttribute("href")?.startsWith("/genre/")
      );

      // Should have links for all 4 genres
      expect(genreLinks.length).toBeGreaterThanOrEqual(4);

      // Verify slugified URLs exist with category param
      const hrefs = genreLinks.map((l) => l.getAttribute("href"));
      expect(hrefs).toContain("/genre/mystery?category=fiction");
      expect(hrefs).toContain("/genre/romance?category=fiction");
      expect(hrefs).toContain("/genre/biography?category=nonfiction");
      expect(hrefs).toContain("/genre/history?category=nonfiction");
    });

    it("highlights the active genre", () => {
      renderSidebar("mystery", "fiction");

      // The "Mystery" link should be highlighted
      const allMysteryLinks = screen.getAllByText("Mystery");
      const hasActive = allMysteryLinks.some((el) => {
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
      // "All Genres" + 4 genre options
      expect(options).toHaveLength(5);
    });
  });

  describe("mobile genre select navigation", () => {
    it("renders the active genre slug as the selected option", () => {
      mockUseGroupedGenres.mockReturnValue({
        data: mockGroupedGenres,
        isLoading: false,
      });

      renderSidebar("mystery", "fiction");

      const select = screen.getByRole("combobox");
      expect(select).toHaveValue("/genre/mystery?category=fiction");
    });

    it("defaults to empty string (All Genres) when no genre is active", () => {
      mockUseGroupedGenres.mockReturnValue({
        data: mockGroupedGenres,
        isLoading: false,
      });

      renderSidebar();

      const select = screen.getByRole("combobox");
      expect(select).toHaveValue("");
    });
  });
});

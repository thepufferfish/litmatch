import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RecommendationGrid } from "./RecommendationGrid";
import type { RecommendationResponse, GroupedGenres } from "@/types";
import * as useGroupedGenresHook from "@/hooks/useGroupedGenres";
import * as useRecommendationsHook from "@/hooks/useRecommendations";

// -- Test data ---------------------------------------------------------------

const fictionBooks: RecommendationResponse = {
  items: [
    {
      id: 1,
      title: "Fiction Book One",
      author_id: 1,
      publisher_id: 1,
      publish_date: "2024-01-01",
      description: "A fiction book.",
      url: "https://example.com/fiction1",
      cover: null,
      author: { id: 1, name: "Fiction Author" },
      publisher: { id: 1, name: "Publisher" },
      genres: [{ id: 1, name: "Fiction" }],
      avg_critic_rating: 4.0,
      review_count: 10,
    },
  ],
  meta: {
    strategy: "personalized",
    rating_count: 8,
    category: "fiction",
  },
};

const nonfictionBooks: RecommendationResponse = {
  items: [
    {
      id: 2,
      title: "Nonfiction Book One",
      author_id: 2,
      publisher_id: 2,
      publish_date: "2024-02-01",
      description: "A nonfiction book.",
      url: "https://example.com/nonfiction1",
      cover: null,
      author: { id: 2, name: "Nonfiction Author" },
      publisher: { id: 2, name: "Publisher" },
      genres: [{ id: 2, name: "History" }],
      avg_critic_rating: 3.5,
      review_count: 7,
    },
  ],
  meta: {
    strategy: "popular",
    rating_count: 2,
    category: "nonfiction",
  },
};

const emptyResponse: RecommendationResponse = {
  items: [],
  meta: {
    strategy: "popular",
    rating_count: 0,
    category: "fiction",
  },
};

const mockGroupedGenres: GroupedGenres = {
  fiction: [{ id: 1, name: "Mystery" }],
  nonfiction: [{ id: 2, name: "History" }],
  unknown: [],
};

// -- Helpers -----------------------------------------------------------------

function renderGrid(props?: {
  fiction?: RecommendationResponse;
  nonfiction?: RecommendationResponse;
  genresLoading?: boolean;
}) {
  const {
    fiction = fictionBooks,
    nonfiction = nonfictionBooks,
    genresLoading = false,
  } = props ?? {};

  // Mock the hooks
  vi.spyOn(useGroupedGenresHook, "useGroupedGenres").mockReturnValue({
    data: genresLoading ? undefined : mockGroupedGenres,
    isLoading: genresLoading,
  } as ReturnType<typeof useGroupedGenresHook.useGroupedGenres>);

  vi.spyOn(useRecommendationsHook, "useRecommendations").mockImplementation(
    (params) => {
      const category = params?.category ?? "all";
      if (category === "fiction") {
        return {
          data: fiction,
          isLoading: false,
        } as ReturnType<typeof useRecommendationsHook.useRecommendations>;
      }
      return {
        data: nonfiction,
        isLoading: false,
      } as ReturnType<typeof useRecommendationsHook.useRecommendations>;
    }
  );

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RecommendationGrid isAuthenticated={true} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// -- Tests -------------------------------------------------------------------

describe("RecommendationGrid", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders fiction tab by default", async () => {
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("Fiction Book One")).toBeInTheDocument();
    });
    expect(screen.queryByText("Nonfiction Book One")).not.toBeInTheDocument();
  });

  it("renders nonfiction tab when clicked", async () => {
    const user = userEvent.setup();
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("Fiction Book One")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("tab", { name: /non-fiction/i }));

    expect(screen.getByText("Nonfiction Book One")).toBeInTheDocument();
    expect(screen.queryByText("Fiction Book One")).not.toBeInTheDocument();
  });

  it("shows strategy label 'based on your taste' for personalized", async () => {
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText(/based on your taste/i)).toBeInTheDocument();
    });
  });

  it("shows strategy label 'popular picks' for popular", async () => {
    const user = userEvent.setup();
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("Fiction Book One")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("tab", { name: /non-fiction/i }));

    await waitFor(() => {
      expect(screen.getByText(/popular picks/i)).toBeInTheDocument();
    });
  });

  it("shows loading skeleton when hooks are loading", () => {
    const { container } = renderGrid({ genresLoading: true });

    const skeletons = container.querySelectorAll(".skeleton-shimmer");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows empty state when active tab has no items", async () => {
    renderGrid({ fiction: emptyResponse });

    await waitFor(() => {
      expect(
        screen.getByText(/no.*fiction recommendations yet/i)
      ).toBeInTheDocument();
    });
  });

  it("shows nonfiction empty state", async () => {
    const user = userEvent.setup();
    renderGrid({
      nonfiction: {
        ...emptyResponse,
        meta: { ...emptyResponse.meta, category: "nonfiction" },
      },
    });

    await waitFor(() => {
      expect(screen.getByText("Fiction Book One")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("tab", { name: /non-fiction/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/no.*non-fiction recommendations yet/i)
      ).toBeInTheDocument();
    });
  });

  it("renders book cards within the active tab", async () => {
    renderGrid();

    await waitFor(() => {
      const links = screen.getAllByRole("link");
      expect(
        links.some((link) => link.getAttribute("href") === "/books/1")
      ).toBe(true);
    });
  });
});

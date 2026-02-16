import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RecommendationGrid } from "./RecommendationGrid";
import type { PaginatedRecommendationResponse, GroupedGenres } from "@/types";
import * as useGroupedGenresHook from "@/hooks/useGroupedGenres";
import * as useInfiniteRecommendationsHook from "@/hooks/useInfiniteRecommendations";

// -- Test data ---------------------------------------------------------------

const fictionPage: PaginatedRecommendationResponse = {
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
  total: 1,
  offset: 0,
  limit: 20,
  has_more: false,
};

const nonfictionPage: PaginatedRecommendationResponse = {
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
  total: 1,
  offset: 0,
  limit: 20,
  has_more: false,
};

const emptyPage: PaginatedRecommendationResponse = {
  items: [],
  meta: {
    strategy: "popular",
    rating_count: 0,
    category: "fiction",
  },
  total: 0,
  offset: 0,
  limit: 20,
  has_more: false,
};

const fictionPageWithMore: PaginatedRecommendationResponse = {
  ...fictionPage,
  total: 40,
  has_more: true,
};

const mockGroupedGenres: GroupedGenres = {
  fiction: [{ id: 1, name: "Mystery" }],
  nonfiction: [{ id: 2, name: "History" }],
  unknown: [],
};

// -- Helpers -----------------------------------------------------------------

function makeInfiniteQueryResult(
  pages: PaginatedRecommendationResponse[],
  overrides: Record<string, unknown> = {}
) {
  const lastPage = pages[pages.length - 1];
  return {
    data: { pages, pageParams: pages.map((_, i) => i * 20) },
    isLoading: false,
    isFetchingNextPage: false,
    hasNextPage: pages.length > 0 && lastPage?.has_more === true,
    fetchNextPage: vi.fn(),
    ...overrides,
  };
}

function renderGrid(props?: {
  fictionPages?: PaginatedRecommendationResponse[];
  nonfictionPages?: PaginatedRecommendationResponse[];
  genresLoading?: boolean;
  fictionOverrides?: Record<string, unknown>;
  nonfictionOverrides?: Record<string, unknown>;
}) {
  const {
    fictionPages = [fictionPage],
    nonfictionPages = [nonfictionPage],
    genresLoading = false,
    fictionOverrides = {},
    nonfictionOverrides = {},
  } = props ?? {};

  // Mock the hooks
  vi.spyOn(useGroupedGenresHook, "useGroupedGenres").mockReturnValue({
    data: genresLoading ? undefined : mockGroupedGenres,
    isLoading: genresLoading,
  } as ReturnType<typeof useGroupedGenresHook.useGroupedGenres>);

  vi.spyOn(
    useInfiniteRecommendationsHook,
    "useInfiniteRecommendations"
  ).mockImplementation((params) => {
    const category = params?.category ?? "all";
    if (category === "fiction") {
      return makeInfiniteQueryResult(
        fictionPages,
        fictionOverrides
      ) as unknown as ReturnType<typeof useInfiniteRecommendationsHook.useInfiniteRecommendations>;
    }
    return makeInfiniteQueryResult(
      nonfictionPages,
      nonfictionOverrides
    ) as unknown as ReturnType<typeof useInfiniteRecommendationsHook.useInfiniteRecommendations>;
  });

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
    renderGrid({ fictionPages: [emptyPage] });

    await waitFor(() => {
      expect(
        screen.getByText(/no.*fiction recommendations yet/i)
      ).toBeInTheDocument();
    });
  });

  it("shows nonfiction empty state", async () => {
    const user = userEvent.setup();
    renderGrid({
      nonfictionPages: [
        {
          ...emptyPage,
          meta: { ...emptyPage.meta, category: "nonfiction" },
        },
      ],
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

  // -- Infinite scroll specific tests --

  it("renders sentinel element when has_more is true", async () => {
    renderGrid({ fictionPages: [fictionPageWithMore] });

    await waitFor(() => {
      expect(screen.getByTestId("scroll-sentinel")).toBeInTheDocument();
    });
  });

  it("does not render sentinel element when has_more is false", async () => {
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("Fiction Book One")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("scroll-sentinel")).not.toBeInTheDocument();
  });

  it("shows end-of-list message when no more pages", async () => {
    renderGrid();

    await waitFor(() => {
      expect(
        screen.getByText(/you've seen all recommendations/i)
      ).toBeInTheDocument();
    });
  });

  it("does not show end-of-list message when has_more is true", async () => {
    renderGrid({ fictionPages: [fictionPageWithMore] });

    await waitFor(() => {
      expect(screen.getByText("Fiction Book One")).toBeInTheDocument();
    });

    expect(
      screen.queryByText(/you've seen all recommendations/i)
    ).not.toBeInTheDocument();
  });

  it("flattens items across multiple pages", async () => {
    const page2: PaginatedRecommendationResponse = {
      items: [
        {
          id: 3,
          title: "Fiction Book Two",
          author_id: 3,
          publisher_id: 3,
          publish_date: "2024-03-01",
          description: "Another fiction book.",
          url: "https://example.com/fiction2",
          cover: null,
          author: { id: 3, name: "Another Author" },
          publisher: { id: 3, name: "Publisher" },
          genres: [{ id: 1, name: "Fiction" }],
          avg_critic_rating: 4.5,
          review_count: 12,
        },
      ],
      meta: fictionPage.meta,
      total: 2,
      offset: 20,
      limit: 20,
      has_more: false,
    };

    renderGrid({
      fictionPages: [fictionPageWithMore, page2],
    });

    await waitFor(() => {
      expect(screen.getByText("Fiction Book One")).toBeInTheDocument();
      expect(screen.getByText("Fiction Book Two")).toBeInTheDocument();
    });
  });
});

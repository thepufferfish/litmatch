import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { RecommendationGrid } from "./RecommendationGrid";
import type { RecommendationResponse } from "@/types";

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

// -- Helpers -----------------------------------------------------------------

function renderGrid(props?: {
  fiction?: RecommendationResponse;
  nonfiction?: RecommendationResponse;
  isLoading?: boolean;
}) {
  const {
    fiction = fictionBooks,
    nonfiction = nonfictionBooks,
    isLoading = false,
  } = props ?? {};

  return render(
    <MemoryRouter>
      <RecommendationGrid
        fictionData={fiction}
        nonfictionData={nonfiction}
        isLoading={isLoading}
      />
    </MemoryRouter>
  );
}

// -- Tests -------------------------------------------------------------------

describe("RecommendationGrid", () => {
  it("renders fiction tab by default", () => {
    renderGrid();

    expect(screen.getByText("Fiction Book One")).toBeInTheDocument();
    expect(screen.queryByText("Nonfiction Book One")).not.toBeInTheDocument();
  });

  it("renders nonfiction tab when clicked", async () => {
    const user = userEvent.setup();
    renderGrid();

    await user.click(screen.getByRole("tab", { name: /non-fiction/i }));

    expect(screen.getByText("Nonfiction Book One")).toBeInTheDocument();
    expect(screen.queryByText("Fiction Book One")).not.toBeInTheDocument();
  });

  it("shows strategy label 'Based on your taste' for personalized", () => {
    renderGrid();

    expect(screen.getByText("Based on your taste")).toBeInTheDocument();
  });

  it("shows strategy label 'Popular picks' for popular", async () => {
    const user = userEvent.setup();
    renderGrid();

    await user.click(screen.getByRole("tab", { name: /non-fiction/i }));

    expect(screen.getByText("Popular picks")).toBeInTheDocument();
  });

  it("shows loading skeleton when isLoading is true", () => {
    const { container } = renderGrid({ isLoading: true });

    const skeletons = container.querySelectorAll(".skeleton-shimmer");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows empty state when active tab has no items", () => {
    renderGrid({ fiction: emptyResponse });

    expect(
      screen.getByText("No fiction recommendations yet")
    ).toBeInTheDocument();
  });

  it("shows nonfiction empty state", async () => {
    const user = userEvent.setup();
    renderGrid({
      nonfiction: {
        ...emptyResponse,
        meta: { ...emptyResponse.meta, category: "nonfiction" },
      },
    });

    await user.click(screen.getByRole("tab", { name: /non-fiction/i }));

    expect(
      screen.getByText("No non-fiction recommendations yet")
    ).toBeInTheDocument();
  });

  it("renders book cards within the active tab", () => {
    renderGrid();

    const links = screen.getAllByRole("link");
    expect(links.some((link) => link.getAttribute("href") === "/books/1")).toBe(
      true
    );
  });
});

import { useMemo, useState } from "react";
import type { RecommendationStrategy } from "@/types";
import { BookCard } from "@/components/BookCard";
import { SkeletonGrid, SkeletonRow } from "@/components/Skeleton";
import { SubgenreFilter } from "@/components/SubgenreFilter";
import { useGroupedGenres } from "@/hooks/useGroupedGenres";
import { useInfiniteRecommendations } from "@/hooks/useInfiniteRecommendations";
import { useIntersectionObserver } from "@/hooks/useIntersectionObserver";

type Tab = "fiction" | "nonfiction";

interface RecommendationGridProps {
  userRatings?: Map<number, number>;
  onRate?: (bookId: number, rating: number | null) => void;
  isRatingDisabled?: boolean;
  isAuthenticated?: boolean;
  myListIds?: Set<number>;
  onAddToList?: (bookId: number) => void;
  onRemoveFromList?: (bookId: number) => void;
}

const STRATEGY_LABELS: Record<RecommendationStrategy, string> = {
  personalized: "Based on your taste",
  popular: "Popular picks",
};

export function RecommendationGrid({
  userRatings,
  onRate,
  isRatingDisabled,
  isAuthenticated,
  myListIds,
  onAddToList,
  onRemoveFromList,
}: RecommendationGridProps) {
  const [activeTab, setActiveTab] = useState<Tab>("fiction");
  const [fictionGenreId, setFictionGenreId] = useState<number | undefined>(undefined);
  const [nonfictionGenreId, setNonfictionGenreId] = useState<number | undefined>(undefined);

  const { data: groupedGenres, isLoading: genresLoading } = useGroupedGenres();

  const fictionQuery = useInfiniteRecommendations({
    category: "fiction",
    genreId: fictionGenreId,
    enabled: isAuthenticated,
  });

  const nonfictionQuery = useInfiniteRecommendations({
    category: "nonfiction",
    genreId: nonfictionGenreId,
    enabled: isAuthenticated,
  });

  const activeQuery = activeTab === "fiction" ? fictionQuery : nonfictionQuery;

  const allItems = useMemo(
    () => activeQuery.data?.pages.flatMap((p) => p.items) ?? [],
    [activeQuery.data]
  );

  const meta = activeQuery.data?.pages[0]?.meta;

  const sentinelRef = useIntersectionObserver({
    enabled: activeQuery.hasNextPage && !activeQuery.isFetchingNextPage,
    onIntersect: () => activeQuery.fetchNextPage(),
  });

  const isLoading = fictionQuery.isLoading || nonfictionQuery.isLoading || genresLoading;

  if (isLoading) {
    return <SkeletonGrid count={8} />;
  }

  const activeGenreId = activeTab === "fiction" ? fictionGenreId : nonfictionGenreId;
  const setActiveGenreId = activeTab === "fiction" ? setFictionGenreId : setNonfictionGenreId;
  const activeGenres = activeTab === "fiction" ? groupedGenres?.fiction ?? [] : groupedGenres?.nonfiction ?? [];

  const strategyLabel = meta ? STRATEGY_LABELS[meta.strategy] : undefined;
  const tabLabel = activeTab === "fiction" ? "fiction" : "non-fiction";

  // Find the selected genre name
  const selectedGenre = activeGenreId
    ? activeGenres.find((g) => g.id === activeGenreId)
    : undefined;

  const genreLabel = selectedGenre ? `${selectedGenre.name} ` : "";

  return (
    <div>
      {/* Tab bar */}
      <div className="flex gap-1 mb-4" role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === "fiction"}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
            activeTab === "fiction"
              ? "bg-leather text-white"
              : "bg-parchment text-ink-light hover:bg-parchment-dark"
          }`}
          onClick={() => setActiveTab("fiction")}
        >
          Fiction
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "nonfiction"}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
            activeTab === "nonfiction"
              ? "bg-leather text-white"
              : "bg-parchment text-ink-light hover:bg-parchment-dark"
          }`}
          onClick={() => setActiveTab("nonfiction")}
        >
          Non-Fiction
        </button>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Subgenre filter -- left sidebar on desktop, horizontal pills on mobile/tablet */}
        {groupedGenres && (
          <SubgenreFilter
            genres={activeGenres}
            activeGenreId={activeGenreId}
            onSelect={setActiveGenreId}
          />
        )}

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* Strategy label */}
          {strategyLabel && (
            <p className="text-sm text-muted mb-4">
              {genreLabel}
              {strategyLabel.toLowerCase()}
            </p>
          )}

          {/* Content */}
          {allItems.length === 0 && !activeQuery.isLoading ? (
            <p className="text-muted text-center py-8">
              No {genreLabel}{tabLabel} recommendations yet
            </p>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {allItems.map((book) => (
                  <BookCard
                    key={book.id}
                    book={book}
                    userRating={userRatings?.get(book.id)}
                    onRate={onRate}
                    isRatingDisabled={isRatingDisabled}
                    isAuthenticated={isAuthenticated}
                    isOnList={myListIds?.has(book.id)}
                    onAddToList={onAddToList}
                    onRemoveFromList={onRemoveFromList}
                  />
                ))}
              </div>

              {/* Loading skeleton for next page */}
              {activeQuery.isFetchingNextPage && (
                <div className="mt-6">
                  <SkeletonRow count={4} />
                </div>
              )}

              {/* Sentinel element for intersection observer */}
              {activeQuery.hasNextPage && (
                <div ref={sentinelRef} className="h-4" data-testid="scroll-sentinel" />
              )}

              {/* End of list message */}
              {!activeQuery.hasNextPage && allItems.length > 0 && (
                <p className="text-muted text-center py-8 text-sm">
                  You've seen all recommendations
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

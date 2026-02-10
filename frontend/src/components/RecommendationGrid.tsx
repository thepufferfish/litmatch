import { useState } from "react";
import type { RecommendationResponse, RecommendationStrategy } from "@/types";
import { BookCard } from "@/components/BookCard";
import { SkeletonGrid } from "@/components/Skeleton";

type Tab = "fiction" | "nonfiction";

interface RecommendationGridProps {
  fictionData: RecommendationResponse;
  nonfictionData: RecommendationResponse;
  isLoading: boolean;
}

const STRATEGY_LABELS: Record<RecommendationStrategy, string> = {
  personalized: "Based on your taste",
  popular: "Popular picks",
};

export function RecommendationGrid({
  fictionData,
  nonfictionData,
  isLoading,
}: RecommendationGridProps) {
  const [activeTab, setActiveTab] = useState<Tab>("fiction");

  if (isLoading) {
    return <SkeletonGrid count={8} />;
  }

  const activeData = activeTab === "fiction" ? fictionData : nonfictionData;
  const strategyLabel = STRATEGY_LABELS[activeData.meta.strategy];
  const tabLabel = activeTab === "fiction" ? "fiction" : "non-fiction";

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

      {/* Strategy label */}
      {strategyLabel && (
        <p className="text-sm text-muted mb-4">{strategyLabel}</p>
      )}

      {/* Content */}
      {activeData.items.length === 0 ? (
        <p className="text-muted text-center py-8">
          No {tabLabel} recommendations yet
        </p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {activeData.items.map((book) => (
            <BookCard key={book.id} book={book} />
          ))}
        </div>
      )}
    </div>
  );
}

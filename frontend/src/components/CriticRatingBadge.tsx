interface CriticRatingBadgeProps {
  avgRating: number | null;
  reviewCount: number;
  showCount?: boolean;
}

function getRatingStyle(avg: number): { label: string; className: string } {
  if (avg >= 3.5) return { label: "Rave", className: "bg-rave-bg text-rave" };
  if (avg >= 2.5)
    return { label: "Positive", className: "bg-positive-bg text-positive" };
  if (avg >= 1.5)
    return { label: "Mixed", className: "bg-mixed-bg text-mixed" };
  return { label: "Pan", className: "bg-pan-bg text-pan" };
}

export function CriticRatingBadge({
  avgRating,
  reviewCount,
  showCount = false,
}: CriticRatingBadgeProps) {
  if (avgRating === null || avgRating === undefined) return null;

  const { label, className } = getRatingStyle(avgRating);

  return (
    <div className="flex items-center gap-2" data-testid="critic-rating-badge">
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${className}`}
      >
        {avgRating.toFixed(1)} {label}
      </span>
      {showCount && reviewCount > 0 && (
        <span className="text-xs text-muted">
          from {reviewCount} {reviewCount === 1 ? "review" : "reviews"}
        </span>
      )}
    </div>
  );
}

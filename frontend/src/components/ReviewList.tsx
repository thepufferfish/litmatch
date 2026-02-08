import { useState } from "react";
import type { Review } from "@/types";

interface ReviewListProps {
  reviews: Review[];
}

function getRatingLabel(rating: number): {
  label: string;
  className: string;
} {
  switch (rating) {
    case 4:
      return { label: "Rave", className: "bg-rave-bg text-rave" };
    case 3:
      return { label: "Positive", className: "bg-positive-bg text-positive" };
    case 2:
      return { label: "Mixed", className: "bg-mixed-bg text-mixed" };
    case 1:
      return { label: "Pan", className: "bg-pan-bg text-pan" };
    default:
      return { label: "Unknown", className: "bg-parchment text-muted" };
  }
}

function ReviewItem({ review }: { review: Review }) {
  const { label, className } = getRatingLabel(review.rating);
  const criticName = review.critic?.name ?? "Anonymous";
  const publicationName = review.publication?.name;

  return (
    <article className="py-5 first:pt-0">
      <div className="flex items-start justify-between gap-4 mb-2">
        <div>
          <span className="font-medium text-ink">{criticName}</span>
          {publicationName && (
            <span className="text-muted text-sm ml-1.5">
              &mdash; {publicationName}
            </span>
          )}
        </div>
        <span
          className={`shrink-0 px-2.5 py-0.5 rounded-full text-xs font-semibold ${className}`}
        >
          {label}
        </span>
      </div>
      {review.review && (
        <p className="text-ink-light text-sm leading-relaxed line-clamp-4">
          {review.review}
        </p>
      )}
    </article>
  );
}

export function ReviewList({ reviews }: ReviewListProps) {
  const [expanded, setExpanded] = useState(false);
  const initialCount = 5;
  const displayedReviews = expanded ? reviews : reviews.slice(0, initialCount);
  const hasMore = reviews.length > initialCount;

  if (reviews.length === 0) {
    return (
      <p className="text-muted italic py-4">
        No critic reviews available for this book.
      </p>
    );
  }

  return (
    <div>
      <div className="divide-y divide-parchment">
        {displayedReviews.map((review) => (
          <ReviewItem key={review.id} review={review} />
        ))}
      </div>

      {hasMore && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="mt-4 text-sm font-medium text-leather hover:text-leather-light transition-colors cursor-pointer"
        >
          Show all {reviews.length} reviews
        </button>
      )}
    </div>
  );
}

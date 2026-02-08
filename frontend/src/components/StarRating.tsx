import { useState } from "react";

interface StarRatingProps {
  value: number;
  onChange?: (rating: number) => void;
  disabled?: boolean;
}

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      role="img"
      className={`w-6 h-6 ${filled ? "text-gold fill-gold" : "text-parchment-dark fill-parchment"}`}
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"
      />
    </svg>
  );
}

export function StarRating({ value, onChange, disabled = false }: StarRatingProps) {
  const [hoverValue, setHoverValue] = useState(0);
  const isInteractive = onChange !== undefined && !disabled;
  const displayValue = hoverValue > 0 ? hoverValue : value;

  return (
    <div className="flex gap-1" role="group" aria-label="Star rating">
      {[1, 2, 3, 4, 5].map((star) => {
        const filled = star <= displayValue;

        if (!isInteractive) {
          return (
            <span
              key={star}
              data-testid={`star-${star}`}
              data-filled={String(star <= value)}
            >
              <StarIcon filled={star <= value} />
            </span>
          );
        }

        return (
          <button
            key={star}
            type="button"
            data-testid={`star-${star}`}
            data-filled={String(filled)}
            aria-label={`Rate ${star} star${star > 1 ? "s" : ""}`}
            className="cursor-pointer transition-transform hover:scale-110 focus:outline-none focus-visible:ring-2 focus-visible:ring-leather rounded"
            onClick={() => onChange(star)}
            onMouseEnter={() => setHoverValue(star)}
            onMouseLeave={() => setHoverValue(0)}
          >
            <StarIcon filled={filled} />
          </button>
        );
      })}
    </div>
  );
}

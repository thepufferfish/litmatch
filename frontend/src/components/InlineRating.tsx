import { useNavigate } from "react-router";
import { StarRating } from "@/components/StarRating";

interface InlineRatingProps {
  bookId: number;
  userRating: number | undefined;
  onRate?: (bookId: number, rating: number | null) => void;
  isDisabled?: boolean;
  isAuthenticated: boolean;
}

export function InlineRating({
  bookId,
  userRating,
  onRate,
  isDisabled = false,
  isAuthenticated,
}: InlineRatingProps) {
  const navigate = useNavigate();

  // Prevent parent <Link> (anchor tag) from navigating when clicking the rating area.
  // preventDefault stops the anchor's native navigation,
  // stopPropagation prevents the event from reaching the Link's onClick.
  const handleContainerClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  if (!isAuthenticated) {
    return (
      <div onClick={handleContainerClick} className="mt-2 px-1">
        <span
          role="link"
          tabIndex={0}
          className="text-xs text-muted hover:text-leather transition-colors cursor-pointer"
          onClick={(e) => {
            e.stopPropagation();
            void navigate("/login");
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.stopPropagation();
              void navigate("/login");
            }
          }}
        >
          Log in to rate
        </span>
      </div>
    );
  }

  return (
    <div onClick={handleContainerClick} className="mt-2 px-1">
      <StarRating
        size="sm"
        value={userRating ?? 0}
        onChange={(rating) => onRate?.(bookId, rating)}
        disabled={isDisabled}
      />
    </div>
  );
}

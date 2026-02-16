import { Link } from "react-router";
import type { Book } from "@/types";
import { CriticRatingBadge } from "@/components/CriticRatingBadge";
import { InlineRating } from "@/components/InlineRating";

interface BookCardProps {
  book: Book;
  userRating?: number;
  onRate?: (bookId: number, rating: number | null) => void;
  isRatingDisabled?: boolean;
  isAuthenticated?: boolean;
}

export function BookCard({
  book,
  userRating,
  onRate,
  isRatingDisabled,
  isAuthenticated,
}: BookCardProps) {
  const sortedGenres = [...(book.genres ?? [])].sort((a, b) =>
    a.name.localeCompare(b.name)
  );
  const displayedGenres = sortedGenres.slice(0, 3);
  const remainingCount = sortedGenres.length - 3;

  return (
    <Link
      to={`/books/${book.id}`}
      className="group block rounded-lg overflow-hidden bg-white shadow-sm border border-parchment/60 hover:shadow-md hover:border-parchment-dark transition-all duration-200"
    >
      {/* Cover */}
      <div className="relative aspect-[2/3] overflow-hidden bg-parchment">
        {book.cover ? (
          <img
            src={book.cover}
            alt={`Cover of ${book.title}`}
            className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <svg
              className="w-16 h-16 text-parchment-dark"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
              />
            </svg>
          </div>
        )}

        {/* Description overlay on hover */}
        {book.description && (
          <div className="absolute inset-0 bg-white/85 opacity-0 group-hover:opacity-100 transition-opacity duration-300 p-4 overflow-y-auto">
            <p className="text-sm text-ink leading-relaxed line-clamp-[12]">
              {book.description}
            </p>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        <h3 className="font-serif text-base font-semibold text-ink leading-snug line-clamp-2 group-hover:text-leather transition-colors">
          {book.title}
        </h3>
        <p
          className={`mt-1 text-sm text-muted leading-snug ${!book.author ? "italic" : ""}`}
        >
          {book.author?.name ?? "Unknown Author"}
        </p>

        {book.avg_critic_rating !== null && (
          <div className="mt-2">
            <CriticRatingBadge
              avgRating={book.avg_critic_rating}
              reviewCount={book.review_count}
              showCount
            />
          </div>
        )}

        {/* Genre tags */}
        {displayedGenres.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {displayedGenres.map((genre) => (
              <span
                key={genre.id}
                className="inline-block px-2 py-0.5 text-xs rounded-full bg-parchment text-ink-light"
              >
                {genre.name}
              </span>
            ))}
            {remainingCount > 0 && (
              <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-cream-dark text-muted">
                +{remainingCount} more
              </span>
            )}
          </div>
        )}

        {/* Inline rating */}
        {isAuthenticated !== undefined && (
          <InlineRating
            bookId={book.id}
            userRating={userRating}
            onRate={onRate}
            isDisabled={isRatingDisabled}
            isAuthenticated={isAuthenticated}
          />
        )}
      </div>
    </Link>
  );
}

import { Link } from "react-router";
import type { Book } from "@/types";
import { CriticRatingBadge } from "@/components/CriticRatingBadge";

interface CompactBookCardProps {
  book: Book;
}

export function CompactBookCard({ book }: CompactBookCardProps) {
  return (
    <Link
      to={`/books/${book.id}`}
      className="group block w-40 sm:w-44 md:w-48 shrink-0 snap-start rounded-lg overflow-hidden bg-white shadow-sm border border-parchment/60 hover:shadow-md transition-shadow duration-200"
      data-testid="compact-book-card"
    >
      {/* Cover */}
      <div className="relative aspect-[2/3] overflow-hidden bg-parchment">
        {book.cover ? (
          <img
            src={book.cover}
            alt={`Cover of ${book.title}`}
            className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300"
            loading="lazy"
            decoding="async"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <svg
              className="w-12 h-12 text-parchment-dark"
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
      </div>

      {/* Content */}
      <div className="p-3">
        <h3 className="font-serif text-sm font-semibold text-ink leading-snug line-clamp-2 group-hover:text-leather transition-colors">
          {book.title}
        </h3>
        <p
          className={`mt-1 text-xs leading-snug line-clamp-1 ${!book.author ? "italic text-muted" : "text-muted"}`}
        >
          {book.author?.name ?? "Unknown Author"}
        </p>

        {book.avg_critic_rating !== null && (
          <div className="mt-1.5">
            <CriticRatingBadge
              avgRating={book.avg_critic_rating}
              reviewCount={book.review_count}
            />
          </div>
        )}
      </div>
    </Link>
  );
}

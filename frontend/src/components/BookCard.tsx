import { Link } from "react-router";
import type { Book } from "@/types";

interface BookCardProps {
  book: Book;
}

function BookPlaceholderCover() {
  return (
    <div className="aspect-[2/3] bg-parchment flex items-center justify-center">
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
  );
}

export function BookCard({ book }: BookCardProps) {
  const sortedGenres = [...book.genres].sort((a, b) =>
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
      {book.cover ? (
        <div className="aspect-[2/3] overflow-hidden bg-parchment">
          <img
            src={book.cover}
            alt={`Cover of ${book.title}`}
            className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300"
            loading="lazy"
          />
        </div>
      ) : (
        <BookPlaceholderCover />
      )}

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
      </div>
    </Link>
  );
}

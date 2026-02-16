import { useParams, Link, useNavigate } from "react-router";
import { useBook } from "@/hooks/useBooks";
import { useReviews } from "@/hooks/useReviews";
import { useUserRating, useSubmitRating, useDeleteRating } from "@/hooks/useRatings";
import { useMyListIds, useAddToList, useRemoveFromList } from "@/hooks/useMyList";
import { useAuth } from "@/context/AuthContext";
import { CriticRatingBadge } from "@/components/CriticRatingBadge";
import { ReviewList } from "@/components/ReviewList";
import { StarRating } from "@/components/StarRating";
import { SkeletonDetail } from "@/components/Skeleton";
import { slugify } from "@/utils/slugify";

export function BookDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const bookId = parseInt(id ?? "0", 10);

  const { data: book, isLoading: bookLoading, error: bookError } = useBook(bookId);
  const { data: reviews, isLoading: reviewsLoading } = useReviews(bookId);
  const { user, isAuthenticated } = useAuth();
  const { data: existingRating, isLoading: ratingLoading } = useUserRating(
    bookId,
    user?.id
  );
  const { mutate: submitRating, isPending: isSubmittingRating } =
    useSubmitRating(user?.id);
  const { mutate: deleteRating, isPending: isDeletingRating } =
    useDeleteRating(user?.id);
  const { data: myListIds } = useMyListIds(user?.id);
  const isOnList = myListIds?.has(bookId) ?? false;
  const { mutate: addToList, isPending: isAddingToList } = useAddToList(user?.id);
  const { mutate: removeFromList, isPending: isRemovingFromList } = useRemoveFromList(user?.id);

  if (bookLoading) {
    return (
      <div className="py-4">
        <SkeletonDetail />
      </div>
    );
  }

  if (bookError || !book) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-16 h-16 rounded-full bg-parchment flex items-center justify-center mb-6">
          <svg
            className="w-8 h-8 text-muted"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
            />
          </svg>
        </div>
        <h2 className="font-serif text-2xl text-ink mb-2">Book not found</h2>
        <p className="text-muted mb-6">
          The book you&apos;re looking for doesn&apos;t exist or has been
          removed.
        </p>
        <button
          onClick={() => navigate("/")}
          className="text-leather font-medium hover:text-leather-light transition-colors cursor-pointer"
        >
          Browse all books
        </button>
      </div>
    );
  }

  const sortedGenres = [...(book.genres ?? [])].sort((a, b) =>
    a.name.localeCompare(b.name)
  );

  return (
    <div className="max-w-5xl mx-auto">
      {/* Back navigation */}
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink transition-colors mb-8 cursor-pointer"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15.75 19.5 8.25 12l7.5-7.5"
          />
        </svg>
        Back to browsing
      </button>

      {/* Book detail layout */}
      <div className="flex flex-col md:flex-row gap-10">
        {/* Cover */}
        <div className="w-full md:w-72 lg:w-80 shrink-0">
          {book.cover ? (
            <img
              src={book.cover}
              alt={`Cover of ${book.title}`}
              className="w-full rounded-lg shadow-md"
              loading="lazy"
              decoding="async"
              sizes="(max-width: 768px) 100vw, (max-width: 1024px) 288px, 320px"
            />
          ) : (
            <div className="aspect-[2/3] rounded-lg bg-parchment flex items-center justify-center shadow-md">
              <svg
                className="w-24 h-24 text-parchment-dark"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={0.75}
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

        {/* Book info */}
        <div className="flex-1 min-w-0">
          <h1 className="font-serif text-2xl sm:text-3xl lg:text-4xl font-bold text-ink leading-tight">
            {book.title}
          </h1>

          <p
            className={`mt-3 text-lg ${!book.author ? "italic text-muted" : "text-ink-light"}`}
          >
            {book.author?.name ?? "Unknown Author"}
          </p>

          {/* Publisher & date */}
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
            {book.publisher && <span>{book.publisher.name}</span>}
            {book.publish_date && (
              <span>
                {new Date(book.publish_date).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </span>
            )}
          </div>

          {/* Genre tags */}
          {sortedGenres.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-5">
              {sortedGenres.map((genre) => (
                <Link
                  key={genre.id}
                  to={`/genre/${slugify(genre.name)}`}
                  className="px-3 py-1 rounded-full text-sm bg-parchment text-ink-light hover:bg-parchment-dark transition-colors"
                >
                  {genre.name}
                </Link>
              ))}
            </div>
          )}

          {/* Description */}
          <div className="mt-8">
            <h2 className="font-serif text-xl text-ink mb-3">About this book</h2>
            {book.description ? (
              <p className="text-ink-light leading-relaxed whitespace-pre-line">
                {book.description}
              </p>
            ) : (
              <p className="text-muted italic">No description available.</p>
            )}
          </div>

          {/* Your Rating section */}
          <div className="mt-10">
            <h2 className="font-serif text-xl text-ink mb-4">Your Rating</h2>

            {!isAuthenticated ? (
              <p className="text-muted">
                <Link
                  to="/login"
                  className="text-leather font-medium hover:text-leather-light transition-colors"
                >
                  Log in to rate
                </Link>{" "}
                this book and get personalized recommendations.
              </p>
            ) : ratingLoading ? (
              <div
                data-testid="rating-loading"
                className="h-8 w-40 skeleton-shimmer rounded"
              />
            ) : (
              <div className="flex items-center gap-4">
                <StarRating
                  value={existingRating?.rating ?? 0}
                  onChange={(rating) => {
                    if (rating === null) {
                      deleteRating(bookId);
                    } else {
                      submitRating({ book_id: bookId, rating });
                    }
                  }}
                  disabled={isSubmittingRating || isDeletingRating}
                />
                {existingRating && (
                  <>
                    <span className="text-sm text-muted">
                      You rated this {existingRating.rating}/5
                    </span>
                    <button
                      type="button"
                      onClick={() => deleteRating(bookId)}
                      disabled={isDeletingRating}
                      className="text-sm text-muted hover:text-red-600 transition-colors cursor-pointer disabled:opacity-50"
                      aria-label={`Remove rating for ${book.title}`}
                    >
                      Remove
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          {/* My List section */}
          <div className="mt-6">
            {!isAuthenticated ? (
              <p className="text-muted text-sm">
                <Link
                  to="/login"
                  className="text-leather font-medium hover:text-leather-light transition-colors"
                >
                  Log in
                </Link>{" "}
                to save this book to your reading list.
              </p>
            ) : (
              <button
                type="button"
                onClick={() => {
                  if (isOnList) {
                    removeFromList(bookId);
                  } else {
                    addToList(bookId);
                  }
                }}
                disabled={isAddingToList || isRemovingFromList}
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer disabled:opacity-50 ${
                  isOnList
                    ? "bg-parchment text-ink-light hover:bg-parchment-dark"
                    : "bg-leather text-white hover:bg-leather-light"
                }`}
              >
                <svg
                  className="w-4 h-4"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  fill={isOnList ? "currentColor" : "none"}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z"
                  />
                </svg>
                {isOnList ? "On My List" : "Add to My List"}
              </button>
            )}
          </div>

          {/* Reviews section */}
          <div className="mt-10">
            {book.avg_critic_rating !== null && (
              <div className="mb-4">
                <CriticRatingBadge
                  avgRating={book.avg_critic_rating}
                  reviewCount={book.review_count}
                  showCount
                />
              </div>
            )}
            <h2 className="font-serif text-xl text-ink mb-4">
              Critic Reviews
              {reviews && reviews.length > 0 && (
                <span className="text-base font-sans text-muted ml-2">
                  ({reviews.length})
                </span>
              )}
            </h2>

            {reviewsLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="space-y-2">
                    <div className="h-4 skeleton-shimmer rounded w-1/3" />
                    <div className="h-3 skeleton-shimmer rounded w-full" />
                    <div className="h-3 skeleton-shimmer rounded w-4/5" />
                  </div>
                ))}
              </div>
            ) : (
              <ReviewList reviews={reviews ?? []} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

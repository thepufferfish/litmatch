import { useEffect } from "react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "@/context/AuthContext";
import { useUserProfile } from "@/hooks/useUserProfile";
import { useRecommendations } from "@/hooks/useRecommendations";
import { useUserRatedBooks, useUserRatings } from "@/hooks/useUserRatedBooks";
import { useDeleteRating } from "@/hooks/useRatings";
import { RecommendationGrid } from "@/components/RecommendationGrid";
import { BookCard } from "@/components/BookCard";
import { StarRating } from "@/components/StarRating";
import { SkeletonGrid } from "@/components/Skeleton";
import type { UserRating } from "@/types";

const PERSONALIZED_THRESHOLD = 5;

function buildRatingMap(ratings: UserRating[]): Map<number, number> {
  const map = new Map<number, number>();
  for (const r of ratings) {
    map.set(r.book_id, r.rating);
  }
  return map;
}

function ProfileLoading() {
  return (
    <div className="space-y-8">
      <div className="h-8 skeleton-shimmer rounded w-48" />
      <div className="h-5 skeleton-shimmer rounded w-64" />
      <SkeletonGrid count={4} />
    </div>
  );
}

export function ProfilePage() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();

  const { data: profile, isLoading: profileLoading } = useUserProfile(
    isAuthenticated
  );
  const { data: ratedBooksData, isLoading: ratedBooksLoading } =
    useUserRatedBooks(user?.id);
  const { data: ratingsData, isLoading: ratingsLoading } = useUserRatings(
    user?.id
  );
  const { data: fictionRecs, isLoading: fictionLoading } = useRecommendations({
    category: "fiction",
    enabled: isAuthenticated,
  });
  const { data: nonfictionRecs, isLoading: nonfictionLoading } =
    useRecommendations({
      category: "nonfiction",
      enabled: isAuthenticated,
    });
  const { mutate: deleteRating, isPending: isDeletingRating } =
    useDeleteRating(user?.id);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      void navigate("/login");
    }
  }, [authLoading, isAuthenticated, navigate]);

  if (authLoading) {
    return <ProfileLoading />;
  }

  if (!isAuthenticated || !user) {
    return null;
  }

  const isDataLoading =
    profileLoading || ratedBooksLoading || ratingsLoading;
  const isRecsLoading = fictionLoading || nonfictionLoading;

  if (isDataLoading) {
    return <ProfileLoading />;
  }

  const ratingCount = profile?.rating_count ?? 0;
  const ratedBooks = ratedBooksData?.items ?? [];
  const ratingMap = buildRatingMap(ratingsData ?? []);
  const needsMoreRatings = ratingCount < PERSONALIZED_THRESHOLD;

  return (
    <div className="space-y-10">
      {/* Page heading */}
      <div>
        <h1 className="font-serif text-3xl font-bold text-ink">
          Your Library
        </h1>
        <p className="text-muted mt-1">
          {ratingCount} {ratingCount === 1 ? "book" : "books"} rated
        </p>
      </div>

      {/* My Rated Books section */}
      <section>
        <h2 className="font-serif text-xl font-semibold text-ink mb-4">
          My Rated Books
        </h2>

        {ratedBooks.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg border border-parchment">
            <p className="text-muted mb-4">
              You haven&apos;t rated any books yet.
            </p>
            <Link
              to="/"
              className="inline-flex items-center px-5 py-2.5 rounded-lg bg-leather text-white font-medium hover:bg-leather-light transition-colors"
            >
              Browse books
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {ratedBooks.map((book) => {
              const userRating = ratingMap.get(book.id);
              return (
                <div key={book.id} className="space-y-2">
                  <BookCard book={book} />
                  {userRating !== undefined && (
                    <div className="flex items-center gap-2 px-1">
                      <StarRating value={userRating} />
                      <span className="text-sm text-muted font-medium">
                        {userRating}/5
                      </span>
                      <button
                        type="button"
                        onClick={() => deleteRating(book.id)}
                        disabled={isDeletingRating}
                        className="ml-auto text-xs text-muted hover:text-red-600 transition-colors cursor-pointer disabled:opacity-50"
                        aria-label={`Remove rating for ${book.title}`}
                      >
                        Remove
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Recommendations section */}
      <section>
        <h2 className="font-serif text-xl font-semibold text-ink mb-4">
          Recommended for You
        </h2>

        {needsMoreRatings && ratingCount > 0 && (
          <div className="mb-6 p-4 rounded-lg bg-parchment/50 border border-parchment">
            <p className="text-sm text-ink-light">
              Rate {PERSONALIZED_THRESHOLD - ratingCount} more{" "}
              {PERSONALIZED_THRESHOLD - ratingCount === 1 ? "book" : "books"} to
              unlock personalized recommendations.
            </p>
            <div className="mt-2 h-2 rounded-full bg-parchment overflow-hidden">
              <div
                className="h-full rounded-full bg-leather transition-all"
                style={{
                  width: `${(ratingCount / PERSONALIZED_THRESHOLD) * 100}%`,
                }}
              />
            </div>
          </div>
        )}

        {fictionRecs && nonfictionRecs ? (
          <RecommendationGrid
            fictionData={fictionRecs}
            nonfictionData={nonfictionRecs}
            isLoading={isRecsLoading}
          />
        ) : isRecsLoading ? (
          <SkeletonGrid count={8} />
        ) : null}
      </section>
    </div>
  );
}

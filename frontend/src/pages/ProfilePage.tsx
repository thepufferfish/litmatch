import { useEffect } from "react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "@/context/AuthContext";
import { useUserProfile } from "@/hooks/useUserProfile";
import { useMyListIds, useAddToList, useRemoveFromList } from "@/hooks/useMyList";
import { RecommendationGrid } from "@/components/RecommendationGrid";
import { SkeletonGrid } from "@/components/Skeleton";

const PERSONALIZED_THRESHOLD = 5;

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
  const { data: myListIds } = useMyListIds(user?.id);
  const { mutate: addToList } = useAddToList(user?.id);
  const { mutate: removeFromList } = useRemoveFromList(user?.id);

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

  if (profileLoading) {
    return <ProfileLoading />;
  }

  const ratingCount = profile?.rating_count ?? 0;
  const needsMoreRatings = ratingCount < PERSONALIZED_THRESHOLD;

  return (
    <div className="space-y-10">
      {/* Page heading */}
      <div>
        <h1 className="font-serif text-2xl sm:text-3xl font-bold text-ink">
          Recommended for You
        </h1>
        <p className="text-muted mt-1">
          {ratingCount} {ratingCount === 1 ? "book" : "books"} rated
          {" \u00B7 "}
          <Link
            to="/ratings"
            className="text-leather hover:text-leather-light transition-colors"
          >
            My Ratings
          </Link>
          {" \u00B7 "}
          {profile?.list_count ?? 0} on{" "}
          <Link
            to="/list"
            className="text-leather hover:text-leather-light transition-colors"
          >
            My List
          </Link>
        </p>
      </div>

      {/* Progress toward personalized recommendations */}
      {needsMoreRatings && (
        <div className="p-4 rounded-lg bg-parchment/50 border border-parchment">
          <p className="text-sm text-ink-light">
            Rate {PERSONALIZED_THRESHOLD - ratingCount} more{" "}
            {PERSONALIZED_THRESHOLD - ratingCount === 1 ? "book" : "books"} to
            unlock personalized recommendations.
          </p>
          {ratingCount > 0 && (
            <div className="mt-2 h-2 rounded-full bg-parchment overflow-hidden">
              <div
                className="h-full rounded-full bg-leather transition-all"
                style={{
                  width: `${(ratingCount / PERSONALIZED_THRESHOLD) * 100}%`,
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Recommendations */}
      <section>
        <RecommendationGrid
          isAuthenticated={isAuthenticated}
          myListIds={myListIds}
          onAddToList={addToList}
          onRemoveFromList={removeFromList}
        />
      </section>
    </div>
  );
}

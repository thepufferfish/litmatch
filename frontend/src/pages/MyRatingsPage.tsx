import { useCallback, useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useAuth } from "@/context/AuthContext";
import { useUserRatedBooksPaginated } from "@/hooks/useUserRatedBooks";
import {
  useUserRatingsMap,
  useSubmitRating,
  useDeleteRating,
} from "@/hooks/useRatings";
import { useMyListIds, useAddToList, useRemoveFromList } from "@/hooks/useMyList";
import { BookGrid } from "@/components/BookGrid";
import { SortSelect, SORT_OPTIONS } from "@/components/SortSelect";
import { Pagination } from "@/components/Pagination";
import { SkeletonGrid } from "@/components/Skeleton";
import type { BookSortOption } from "@/types";

const VALID_SORTS = new Set<string>(SORT_OPTIONS.map((o) => o.value));
const PAGE_LIMIT = 12;

function RatingsLoading() {
  return (
    <div className="space-y-8">
      <div className="h-8 skeleton-shimmer rounded w-48" />
      <div className="h-5 skeleton-shimmer rounded w-64" />
      <SkeletonGrid count={PAGE_LIMIT} />
    </div>
  );
}

export function MyRatingsPage() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const page = parseInt(searchParams.get("page") ?? "1", 10) || 1;
  const rawSort = searchParams.get("sort");
  const sort =
    rawSort && VALID_SORTS.has(rawSort)
      ? (rawSort as BookSortOption)
      : undefined;

  const { data: booksData, isLoading: booksLoading } =
    useUserRatedBooksPaginated({ page, limit: PAGE_LIMIT, sort });

  const { data: userRatings } = useUserRatingsMap(user?.id);
  const { mutate: submitRating } = useSubmitRating(user?.id);
  const { mutate: deleteRating } = useDeleteRating(user?.id);
  const { data: myListIds } = useMyListIds(user?.id);
  const { mutate: addToList } = useAddToList(user?.id);
  const { mutate: removeFromList } = useRemoveFromList(user?.id);

  const handleRate = useCallback(
    (bookId: number, rating: number | null) => {
      if (rating === null) {
        deleteRating(bookId);
        return;
      }
      if (!Number.isInteger(rating) || rating < 1 || rating > 5) return;
      submitRating({ book_id: bookId, rating });
    },
    [submitRating, deleteRating]
  );

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      void navigate("/login");
    }
  }, [authLoading, isAuthenticated, navigate]);

  // Redirect to page 1 when current page exceeds total pages
  useEffect(() => {
    if (booksData && booksData.total > 0 && booksData.limit > 0) {
      const totalPages = Math.ceil(booksData.total / booksData.limit);
      if (page > totalPages) {
        const params = new URLSearchParams(searchParams);
        params.delete("page");
        setSearchParams(params, { replace: true });
      }
    }
  }, [booksData, page, searchParams, setSearchParams]);

  if (authLoading) {
    return <RatingsLoading />;
  }

  if (!isAuthenticated || !user) {
    return null;
  }

  const items = booksData?.items ?? [];
  const total = booksData?.total ?? 0;
  const totalPages =
    booksData && booksData.limit > 0
      ? Math.ceil((booksData.total ?? 0) / booksData.limit)
      : 0;
  const isEmpty = !booksLoading && items.length === 0;

  const handlePageChange = (newPage: number) => {
    const params = new URLSearchParams(searchParams);
    if (newPage === 1) {
      params.delete("page");
    } else {
      params.set("page", String(newPage));
    }
    setSearchParams(params);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleSortChange = (newSort: BookSortOption | undefined) => {
    const params = new URLSearchParams(searchParams);
    if (newSort) {
      params.set("sort", newSort);
    } else {
      params.delete("sort");
    }
    params.delete("page");
    setSearchParams(params);
  };

  return (
    <div className="space-y-8">
      {/* Page heading */}
      <div>
        <h1 className="font-serif text-2xl sm:text-3xl font-bold text-ink">My Ratings</h1>
        <p className="text-muted mt-1">
          {total} {total === 1 ? "book" : "books"} rated
        </p>
      </div>

      {isEmpty ? (
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
        <>
          {/* Sort control */}
          <div className="flex justify-end">
            <SortSelect value={sort} onChange={handleSortChange} />
          </div>

          {/* Book grid */}
          <BookGrid
            books={items}
            isLoading={booksLoading}
            userRatings={userRatings}
            onRate={handleRate}
            isAuthenticated={isAuthenticated}
            myListIds={myListIds}
            onAddToList={addToList}
            onRemoveFromList={removeFromList}
          />

          {/* Pagination */}
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={handlePageChange}
          />
        </>
      )}
    </div>
  );
}

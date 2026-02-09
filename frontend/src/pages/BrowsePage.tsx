import { useEffect, useMemo } from "react";
import {
  useSearchParams,
  useParams,
  useNavigate,
  Link,
} from "react-router";
import { useBooks, useSearchBooks } from "@/hooks/useBooks";
import { useGenres } from "@/hooks/useGenres";
import { BookGrid } from "@/components/BookGrid";
import { GenreSidebar } from "@/components/GenreSidebar";
import { SearchBar } from "@/components/SearchBar";
import { Pagination } from "@/components/Pagination";
import { slugify } from "@/utils/slugify";

export function BrowsePage() {
  const { slug: genreSlug } = useParams<{ slug: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const { data: genres } = useGenres();

  // Resolve slug → genre ID using the genres list
  const resolvedGenre = useMemo(() => {
    if (!genreSlug || !genres) return undefined;
    return genres.find((g) => slugify(g.name) === genreSlug);
  }, [genreSlug, genres]);

  const genreId = resolvedGenre?.id;
  const page = parseInt(searchParams.get("page") ?? "1", 10) || 1;
  const searchQuery = searchParams.get("search") ?? "";

  // Determine which query to use
  const isSearching = searchQuery.length >= 2;

  const booksQuery = useBooks({
    page,
    genre: genreId,
  });

  const searchBooksQuery = useSearchBooks({
    q: searchQuery,
    page,
  });

  const activeQuery = isSearching ? searchBooksQuery : booksQuery;
  const { data, isLoading } = activeQuery;
  const items = data?.items ?? [];

  // Find the active genre name for the empty state message
  const activeGenreName = resolvedGenre?.name ?? null;

  // Check if genre slug is invalid (genres loaded but no match found)
  const genreNotFound = genreSlug && genres && !resolvedGenre;

  // Redirect if page exceeds total
  useEffect(() => {
    if (
      data &&
      items.length === 0 &&
      data.total > 0 &&
      data.page > 1
    ) {
      const params = new URLSearchParams(searchParams);
      params.delete("page");
      setSearchParams(params, { replace: true });
    }
  }, [data, items, searchParams, setSearchParams]);

  const totalPages = data && data.limit > 0
    ? Math.ceil((data.total ?? 0) / data.limit)
    : 0;

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

  const handleSearch = (query: string) => {
    // When searching, reset to page 1 and clear genre
    if (genreSlug) {
      navigate(`/?search=${encodeURIComponent(query)}`);
    } else {
      const params = new URLSearchParams();
      params.set("search", query);
      setSearchParams(params);
    }
  };

  const handleClearSearch = () => {
    const params = new URLSearchParams(searchParams);
    params.delete("search");
    params.delete("page");
    setSearchParams(params);
  };

  // Determine empty state: show when not loading and either:
  // - data has not arrived yet (undefined)
  // - data.items is missing or empty
  const isEmpty = !isLoading && (
    !data || items.length === 0
  );

  // Handle genre not found
  if (genreNotFound) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-20 h-20 rounded-full bg-parchment flex items-center justify-center mb-6">
          <svg
            className="w-10 h-10 text-muted-light"
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
        <h2 className="font-serif text-2xl text-ink mb-2">Genre not found</h2>
        <p className="text-muted mb-6">
          The genre you&apos;re looking for doesn&apos;t exist.
        </p>
        <Link
          to="/"
          className="inline-flex items-center px-5 py-2.5 rounded-lg bg-leather text-white font-medium hover:bg-leather-light transition-colors"
        >
          Browse all books
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row gap-8">
      <GenreSidebar activeGenreSlug={genreSlug} />

      <main className="flex-1 min-w-0">
        {/* Search bar */}
        <div className="mb-8">
          <SearchBar
            initialValue={searchQuery}
            onSearch={handleSearch}
            onClear={handleClearSearch}
          />
        </div>

        {/* Active filters indicator */}
        {isSearching && (
          <div className="mb-4 flex items-center gap-2 text-sm text-muted">
            <span>
              Showing results for &ldquo;
              <span className="font-medium text-ink">{searchQuery}</span>
              &rdquo;
            </span>
            {data && (
              <span className="text-muted-light">
                ({data.total} {data.total === 1 ? "result" : "results"})
              </span>
            )}
          </div>
        )}

        {activeGenreName && !isSearching && (
          <div className="mb-6">
            <h2 className="font-serif text-2xl text-ink">{activeGenreName}</h2>
          </div>
        )}

        {/* Content */}
        {isEmpty ? (
          <EmptyState
            isSearching={isSearching}
            searchQuery={searchQuery}
            genreName={activeGenreName}
            onClearSearch={handleClearSearch}
          />
        ) : (
          <>
            <BookGrid books={items} isLoading={isLoading} />
            <Pagination
              currentPage={page}
              totalPages={totalPages}
              onPageChange={handlePageChange}
            />
          </>
        )}
      </main>
    </div>
  );
}

function EmptyState({
  isSearching,
  searchQuery,
  genreName,
  onClearSearch,
}: {
  isSearching: boolean;
  searchQuery: string;
  genreName: string | null;
  onClearSearch: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-20 h-20 rounded-full bg-parchment flex items-center justify-center mb-6">
        <svg
          className="w-10 h-10 text-muted-light"
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

      {isSearching ? (
        <>
          <p className="text-lg text-ink mb-2">
            No books found for &ldquo;{searchQuery}&rdquo;.
          </p>
          <button
            onClick={onClearSearch}
            className="mt-2 text-leather font-medium hover:text-leather-light transition-colors cursor-pointer"
          >
            Clear search
          </button>
        </>
      ) : genreName ? (
        <>
          <p className="text-lg text-ink mb-2">
            No books in {genreName} yet.
          </p>
          <Link
            to="/"
            className="mt-2 text-leather font-medium hover:text-leather-light transition-colors"
          >
            Browse all books
          </Link>
        </>
      ) : (
        <p className="text-lg text-muted">
          No books available yet. Check back soon!
        </p>
      )}
    </div>
  );
}

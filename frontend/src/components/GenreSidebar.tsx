import { Link, useNavigate } from "react-router";
import { useGenres } from "@/hooks/useGenres";
import { slugify } from "@/utils/slugify";

interface GenreSidebarProps {
  activeGenreSlug?: string;
}

export function GenreSidebar({ activeGenreSlug }: GenreSidebarProps) {
  const { data: genres, isLoading } = useGenres();

  if (isLoading) {
    return (
      <>
        {/* Desktop skeleton */}
        <aside className="hidden lg:block w-56 shrink-0">
          <div className="sticky top-24 space-y-1">
            <div className="h-5 skeleton-shimmer rounded w-20 mb-3" />
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-8 skeleton-shimmer rounded w-full" />
            ))}
          </div>
        </aside>
        {/* Tablet/mobile skeleton */}
        <div className="lg:hidden mb-4">
          <div className="h-10 skeleton-shimmer rounded-xl w-full" />
        </div>
      </>
    );
  }

  if (!genres?.length) return null;

  const sortedGenres = [...genres].sort((a, b) =>
    a.name.localeCompare(b.name)
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden lg:block w-56 shrink-0">
        <nav className="sticky top-24">
          <h3 className="font-serif text-lg text-ink mb-3 px-3">Genres</h3>
          <ul className="space-y-0.5">
            <li>
              <Link
                to="/"
                className={`block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  !activeGenreSlug
                    ? "bg-leather text-white"
                    : "text-ink-light hover:bg-parchment"
                }`}
              >
                All Books
              </Link>
            </li>
            {sortedGenres.map((genre) => {
              const slug = slugify(genre.name);
              return (
                <li key={genre.id}>
                  <Link
                    to={`/genre/${slug}`}
                    className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
                      activeGenreSlug === slug
                        ? "bg-leather text-white font-medium"
                        : "text-ink-light hover:bg-parchment"
                    }`}
                  >
                    {genre.name}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>

      {/* Tablet: horizontal scrollable chips */}
      <div className="hidden md:flex lg:hidden gap-2 mb-6 overflow-x-auto pb-2 scrollbar-thin">
        <Link
          to="/"
          className={`shrink-0 px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
            !activeGenreSlug
              ? "bg-leather text-white"
              : "bg-parchment text-ink-light hover:bg-parchment-dark"
          }`}
        >
          All
        </Link>
        {sortedGenres.map((genre) => {
          const slug = slugify(genre.name);
          return (
            <Link
              key={genre.id}
              to={`/genre/${slug}`}
              className={`shrink-0 px-4 py-1.5 rounded-full text-sm transition-colors ${
                activeGenreSlug === slug
                  ? "bg-leather text-white font-medium"
                  : "bg-parchment text-ink-light hover:bg-parchment-dark"
              }`}
            >
              {genre.name}
            </Link>
          );
        })}
      </div>

      {/* Mobile: dropdown select */}
      <div className="md:hidden mb-4">
        <MobileGenreSelect
          genres={sortedGenres}
          activeGenreSlug={activeGenreSlug}
        />
      </div>
    </>
  );
}

function MobileGenreSelect({
  genres,
  activeGenreSlug,
}: {
  genres: { id: number; name: string }[];
  activeGenreSlug?: string;
}) {
  const navigate = useNavigate();

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (val === "") {
      navigate("/");
    } else {
      navigate(`/genre/${val}`);
    }
  };

  return (
    <select
      value={activeGenreSlug ?? ""}
      onChange={handleChange}
      className="w-full px-4 py-2.5 rounded-xl border border-parchment-dark bg-white text-ink text-sm focus:outline-none focus:ring-2 focus:ring-leather/30 focus:border-leather cursor-pointer"
    >
      <option value="">All Genres</option>
      {genres.map((genre) => (
        <option key={genre.id} value={slugify(genre.name)}>
          {genre.name}
        </option>
      ))}
    </select>
  );
}

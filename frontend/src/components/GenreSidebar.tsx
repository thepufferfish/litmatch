import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useGroupedGenres } from "@/hooks/useGroupedGenres";
import { slugify } from "@/utils/slugify";
import type { Genre } from "@/types";

function sortGenres(genres: Genre[]): Genre[] {
  return [...genres].sort((a, b) => a.name.localeCompare(b.name));
}

interface GenreSidebarProps {
  activeGenreSlug?: string;
  activeCategory?: "fiction" | "nonfiction";
}

export function GenreSidebar({ activeGenreSlug, activeCategory }: GenreSidebarProps) {
  const { data: groupedGenres, isLoading, isError } = useGroupedGenres();
  const [expandedSection, setExpandedSection] = useState<"fiction" | "nonfiction" | null>(
    activeCategory ?? "fiction"
  );

  const fictionGenres = useMemo(
    () => sortGenres(groupedGenres?.fiction ?? []),
    [groupedGenres]
  );
  const nonfictionGenres = useMemo(
    () => sortGenres(groupedGenres?.nonfiction ?? []),
    [groupedGenres]
  );

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

  if (isError) {
    return (
      <aside className="hidden lg:block w-56 shrink-0">
        <div className="sticky top-24 px-3 py-4 text-sm text-red-600">
          Failed to load genres. Please try again.
        </div>
      </aside>
    );
  }

  if (!groupedGenres) return null;

  // Return null if no genres at all
  if (fictionGenres.length === 0 && nonfictionGenres.length === 0) {
    return null;
  }

  const toggleSection = (section: "fiction" | "nonfiction") => {
    setExpandedSection(expandedSection === section ? null : section);
  };

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

            {/* Fiction section */}
            <li className="mt-4">
              <button
                onClick={() => toggleSection("fiction")}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium text-ink hover:bg-parchment transition-colors cursor-pointer"
              >
                <span>Fiction</span>
                <svg
                  className={`w-4 h-4 transition-transform ${
                    expandedSection === "fiction" ? "rotate-180" : ""
                  }`}
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                </svg>
              </button>
              {expandedSection === "fiction" && (
                <ul className="mt-1 ml-3 space-y-0.5">
                  {fictionGenres.map((genre) => {
                    const slug = slugify(genre.name);
                    return (
                      <li key={genre.id}>
                        <Link
                          to={`/genre/${slug}?category=fiction`}
                          className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
                            activeGenreSlug === slug && activeCategory === "fiction"
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
              )}
            </li>

            {/* Non-Fiction section */}
            <li className="mt-2">
              <button
                onClick={() => toggleSection("nonfiction")}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium text-ink hover:bg-parchment transition-colors cursor-pointer"
              >
                <span>Non-Fiction</span>
                <svg
                  className={`w-4 h-4 transition-transform ${
                    expandedSection === "nonfiction" ? "rotate-180" : ""
                  }`}
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                </svg>
              </button>
              {expandedSection === "nonfiction" && (
                <ul className="mt-1 ml-3 space-y-0.5">
                  {nonfictionGenres.map((genre) => {
                    const slug = slugify(genre.name);
                    return (
                      <li key={genre.id}>
                        <Link
                          to={`/genre/${slug}?category=nonfiction`}
                          className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
                            activeGenreSlug === slug && activeCategory === "nonfiction"
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
              )}
            </li>
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
        {fictionGenres.map((genre) => {
          const slug = slugify(genre.name);
          return (
            <Link
              key={genre.id}
              to={`/genre/${slug}?category=fiction`}
              className={`shrink-0 px-4 py-1.5 rounded-full text-sm transition-colors ${
                activeGenreSlug === slug && activeCategory === "fiction"
                  ? "bg-leather text-white font-medium"
                  : "bg-parchment text-ink-light hover:bg-parchment-dark"
              }`}
            >
              {genre.name}
            </Link>
          );
        })}
        {nonfictionGenres.map((genre) => {
          const slug = slugify(genre.name);
          return (
            <Link
              key={genre.id}
              to={`/genre/${slug}?category=nonfiction`}
              className={`shrink-0 px-4 py-1.5 rounded-full text-sm transition-colors ${
                activeGenreSlug === slug && activeCategory === "nonfiction"
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
          groupedGenres={groupedGenres}
          activeGenreSlug={activeGenreSlug}
          activeCategory={activeCategory}
        />
      </div>
    </>
  );
}

function MobileGenreSelect({
  groupedGenres,
  activeGenreSlug,
  activeCategory,
}: {
  groupedGenres: { fiction: Genre[]; nonfiction: Genre[]; unknown: Genre[] };
  activeGenreSlug?: string;
  activeCategory?: "fiction" | "nonfiction";
}) {
  const navigate = useNavigate();

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (val === "") {
      navigate("/");
    } else {
      navigate(val);
    }
  };

  const currentValue = activeGenreSlug
    ? `/genre/${activeGenreSlug}?category=${activeCategory ?? "fiction"}`
    : "";

  const fictionGenres = useMemo(
    () => sortGenres(groupedGenres.fiction),
    [groupedGenres.fiction]
  );
  const nonfictionGenres = useMemo(
    () => sortGenres(groupedGenres.nonfiction),
    [groupedGenres.nonfiction]
  );

  return (
    <select
      value={currentValue}
      onChange={handleChange}
      className="w-full px-4 py-2.5 rounded-xl border border-parchment-dark bg-white text-ink text-sm focus:outline-none focus:ring-2 focus:ring-leather/30 focus:border-leather cursor-pointer"
    >
      <option value="">All Genres</option>
      <optgroup label="Fiction">
        {fictionGenres.map((genre) => (
          <option
            key={genre.id}
            value={`/genre/${slugify(genre.name)}?category=fiction`}
          >
            {genre.name}
          </option>
        ))}
      </optgroup>
      <optgroup label="Non-Fiction">
        {nonfictionGenres.map((genre) => (
          <option
            key={genre.id}
            value={`/genre/${slugify(genre.name)}?category=nonfiction`}
          >
            {genre.name}
          </option>
        ))}
      </optgroup>
    </select>
  );
}

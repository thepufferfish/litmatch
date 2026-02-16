import { useMemo } from "react";
import type { Genre } from "@/types";

interface SubgenreFilterProps {
  genres: Genre[];
  activeGenreId: number | undefined;
  onSelect: (id: number | undefined) => void;
}

export function SubgenreFilter({
  genres,
  activeGenreId,
  onSelect,
}: SubgenreFilterProps) {
  const sorted = useMemo(
    () => [...genres].sort((a, b) => a.name.localeCompare(b.name)),
    [genres]
  );

  if (sorted.length === 0) return null;

  return (
    <>
      {/* Desktop: vertical sidebar list with independent scroll */}
      <aside className="hidden lg:block w-48 shrink-0">
        <nav
          className="sticky top-[68px] max-h-[calc(100vh-5rem)] flex flex-col"
          role="radiogroup"
          aria-label="Genre filter"
        >
          <h4 className="font-serif text-sm text-muted uppercase tracking-wide mb-3 px-3 shrink-0">
            Subgenre
          </h4>
          <ul className="space-y-0.5 overflow-y-auto scrollbar-thin pr-1">
            <li>
              <button
                onClick={() => onSelect(undefined)}
                role="radio"
                aria-checked={activeGenreId === undefined}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                  activeGenreId === undefined
                    ? "bg-leather text-white"
                    : "text-ink-light hover:bg-parchment"
                }`}
              >
                All
              </button>
            </li>
            {sorted.map((genre) => (
              <li key={genre.id}>
                <button
                  onClick={() => onSelect(genre.id)}
                  role="radio"
                  aria-checked={activeGenreId === genre.id}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors cursor-pointer ${
                    activeGenreId === genre.id
                      ? "bg-leather text-white font-medium"
                      : "text-ink-light hover:bg-parchment"
                  }`}
                >
                  {genre.name}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      {/* Tablet/mobile: horizontal scrollable pills */}
      <div
        role="radiogroup"
        aria-label="Genre filter"
        className="lg:hidden flex gap-2 overflow-x-auto pb-2 scrollbar-thin mb-4"
      >
        <button
          onClick={() => onSelect(undefined)}
          role="radio"
          aria-checked={activeGenreId === undefined}
          className={`shrink-0 px-4 py-1.5 rounded-full text-sm font-medium transition-colors cursor-pointer ${
            activeGenreId === undefined
              ? "bg-leather text-white"
              : "bg-parchment text-ink-light hover:bg-parchment-dark"
          }`}
        >
          All
        </button>
        {sorted.map((genre) => (
          <button
            key={genre.id}
            onClick={() => onSelect(genre.id)}
            role="radio"
            aria-checked={activeGenreId === genre.id}
            className={`shrink-0 px-4 py-1.5 rounded-full text-sm transition-colors cursor-pointer ${
              activeGenreId === genre.id
                ? "bg-leather text-white font-medium"
                : "bg-parchment text-ink-light hover:bg-parchment-dark"
            }`}
          >
            {genre.name}
          </button>
        ))}
      </div>
    </>
  );
}

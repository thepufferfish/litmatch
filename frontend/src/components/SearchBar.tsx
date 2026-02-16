import { useState, useCallback, useEffect } from "react";
import type { FormEvent } from "react";

interface SearchBarProps {
  initialValue?: string;
  onSearch: (query: string) => void;
  onClear: () => void;
}

export function SearchBar({ initialValue = "", onSearch, onClear }: SearchBarProps) {
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    setValue(initialValue);
  }, [initialValue]);

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const trimmed = value.trim();
      if (trimmed.length >= 2) {
        onSearch(trimmed);
      }
    },
    [value, onSearch]
  );

  const handleClear = useCallback(() => {
    setValue("");
    onClear();
  }, [onClear]);

  return (
    <form onSubmit={handleSubmit} className="relative w-full max-w-full sm:max-w-xl">
      <div className="relative">
        <svg
          className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-muted"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
          />
        </svg>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Search by title or author..."
          className="w-full pl-11 pr-20 py-3 rounded-xl border border-parchment-dark bg-white text-ink placeholder:text-muted-light focus:outline-none focus:ring-2 focus:ring-leather/30 focus:border-leather transition-all"
        />
        {value && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-14 top-1/2 -translate-y-1/2 p-2.5 rounded-full hover:bg-parchment text-muted hover:text-ink transition-colors cursor-pointer"
            aria-label="Clear search"
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
                d="M6 18 18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
        <button
          type="submit"
          disabled={value.trim().length < 2}
          className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2.5 rounded-lg bg-leather text-white text-sm font-medium hover:bg-leather-light disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
        >
          Search
        </button>
      </div>
    </form>
  );
}

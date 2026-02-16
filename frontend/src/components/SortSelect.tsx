import type { BookSortOption } from "@/types";

interface SortSelectProps {
  value: BookSortOption | undefined;
  onChange: (sort: BookSortOption | undefined) => void;
}

const SORT_OPTIONS: { value: BookSortOption; label: string }[] = [
  { value: "rating_desc", label: "Highest Rated" },
  { value: "reviews_desc", label: "Most Reviewed" },
  { value: "date_desc", label: "Newest First" },
  { value: "date_asc", label: "Oldest First" },
  { value: "title_asc", label: "Title A\u2013Z" },
  { value: "title_desc", label: "Title Z\u2013A" },
];

export { SORT_OPTIONS };

export function SortSelect({ value, onChange }: SortSelectProps) {
  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selected = e.target.value;
    onChange(selected === "" ? undefined : (selected as BookSortOption));
  };

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
      <label
        htmlFor="sort-select"
        className="text-sm text-muted whitespace-nowrap"
      >
        Sort by
      </label>
      <select
        id="sort-select"
        data-testid="sort-select"
        value={value ?? ""}
        onChange={handleChange}
        className="w-full sm:w-auto px-3 py-2 rounded-lg border border-parchment-dark bg-white text-ink text-sm focus:outline-none focus:ring-2 focus:ring-leather/30 focus:border-leather transition-all cursor-pointer"
      >
        <option value="">Default</option>
        {SORT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

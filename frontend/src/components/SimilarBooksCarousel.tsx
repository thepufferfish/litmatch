import { useRef, useState, useCallback, useEffect } from "react";
import { useSimilarBooks } from "@/hooks/useSimilarBooks";
import { CompactBookCard } from "@/components/CompactBookCard";
import { SkeletonCarousel } from "@/components/Skeleton";

interface SimilarBooksCarouselProps {
  bookId: number;
  enabled?: boolean;
}

export function SimilarBooksCarousel({
  bookId,
  enabled = true,
}: SimilarBooksCarouselProps) {
  const { data: books, isLoading, isError } = useSimilarBooks(bookId, enabled);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 0);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    updateScrollState();

    el.addEventListener("scroll", updateScrollState, { passive: true });
    window.addEventListener("resize", updateScrollState);

    return () => {
      el.removeEventListener("scroll", updateScrollState);
      window.removeEventListener("resize", updateScrollState);
    };
  }, [updateScrollState, books]);

  const scroll = useCallback((direction: "left" | "right") => {
    const el = scrollRef.current;
    if (!el) return;
    const scrollAmount = el.clientWidth * 0.75;
    el.scrollBy({
      left: direction === "left" ? -scrollAmount : scrollAmount,
      behavior: "smooth",
    });
  }, []);

  if (isLoading) {
    return (
      <div data-testid="similar-books-skeleton">
        <h2 className="font-serif text-lg sm:text-xl text-ink mb-4">
          Critics Also Enjoyed
        </h2>
        <SkeletonCarousel />
      </div>
    );
  }

  if (isError || !books || books.length === 0) {
    return null;
  }

  return (
    <div data-testid="similar-books-carousel">
      <h2 className="font-serif text-lg sm:text-xl text-ink mb-4">
        Critics Also Enjoyed
      </h2>

      <div className="relative">
        {/* Left gradient fade */}
        {canScrollLeft && (
          <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-cream to-transparent z-10 pointer-events-none" />
        )}

        {/* Right gradient fade */}
        {canScrollRight && (
          <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-cream to-transparent z-10 pointer-events-none" />
        )}

        {/* Left arrow button */}
        {canScrollLeft && (
          <button
            type="button"
            onClick={() => scroll("left")}
            className="hidden sm:flex absolute left-0 top-1/2 -translate-y-1/2 z-20 w-9 h-9 items-center justify-center rounded-full bg-white shadow-md border border-parchment/60 text-ink hover:bg-parchment transition-colors cursor-pointer"
            aria-label="Scroll left"
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
          </button>
        )}

        {/* Right arrow button */}
        {canScrollRight && (
          <button
            type="button"
            onClick={() => scroll("right")}
            className="hidden sm:flex absolute right-0 top-1/2 -translate-y-1/2 z-20 w-9 h-9 items-center justify-center rounded-full bg-white shadow-md border border-parchment/60 text-ink hover:bg-parchment transition-colors cursor-pointer"
            aria-label="Scroll right"
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
                d="m8.25 4.5 7.5 7.5-7.5 7.5"
              />
            </svg>
          </button>
        )}

        {/* Scroll container */}
        <div
          ref={scrollRef}
          className="flex gap-4 overflow-x-auto scroll-smooth snap-x snap-mandatory scrollbar-hide px-1 py-1"
          data-testid="similar-books-scroll-container"
        >
          {books.map((book) => (
            <CompactBookCard key={book.id} book={book} />
          ))}
        </div>
      </div>
    </div>
  );
}

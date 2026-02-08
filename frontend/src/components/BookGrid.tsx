import type { Book } from "@/types";
import { BookCard } from "@/components/BookCard";
import { SkeletonGrid } from "@/components/Skeleton";

interface BookGridProps {
  books?: Book[];
  isLoading: boolean;
}

export function BookGrid({ books, isLoading }: BookGridProps) {
  if (isLoading) {
    return <SkeletonGrid count={24} />;
  }

  if (!books?.length) {
    return null;
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
      {books.map((book) => (
        <BookCard key={book.id} book={book} />
      ))}
    </div>
  );
}

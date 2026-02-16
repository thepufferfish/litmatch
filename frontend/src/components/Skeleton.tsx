function SkeletonCard() {
  return (
    <div className="rounded-lg overflow-hidden bg-white shadow-sm border border-parchment">
      <div className="aspect-[2/3] skeleton-shimmer" />
      <div className="p-4 space-y-3">
        <div className="h-5 skeleton-shimmer rounded w-3/4" />
        <div className="h-4 skeleton-shimmer rounded w-1/2" />
        <div className="flex gap-2">
          <div className="h-5 skeleton-shimmer rounded-full w-16" />
          <div className="h-5 skeleton-shimmer rounded-full w-20" />
        </div>
      </div>
    </div>
  );
}

export function SkeletonGrid({ count = 24 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

export function SkeletonRow({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

export function SkeletonDetail() {
  return (
    <div className="max-w-4xl mx-auto animate-pulse">
      <div className="flex flex-col md:flex-row gap-8">
        <div className="w-full md:w-80 shrink-0">
          <div className="aspect-[2/3] skeleton-shimmer rounded-lg" />
        </div>
        <div className="flex-1 space-y-4">
          <div className="h-8 skeleton-shimmer rounded w-3/4" />
          <div className="h-5 skeleton-shimmer rounded w-1/3" />
          <div className="h-5 skeleton-shimmer rounded w-1/4" />
          <div className="space-y-2 pt-4">
            <div className="h-4 skeleton-shimmer rounded w-full" />
            <div className="h-4 skeleton-shimmer rounded w-full" />
            <div className="h-4 skeleton-shimmer rounded w-5/6" />
            <div className="h-4 skeleton-shimmer rounded w-4/6" />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoadingSkeleton({
  lines = 4,
  height = 'h-10',
  className = '',
}: {
  lines?: number;
  height?: string;
  className?: string;
}) {
  return (
    <div className={`space-y-3 animate-pulse ${className}`} aria-label="Loading content">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={`${height} bg-slate-200 dark:bg-slate-800 rounded-lg w-full ${
            i === lines - 1 ? 'w-4/5' : ''
          }`}
        />
      ))}
    </div>
  );
}

export function StatCardSkeleton() {
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 animate-pulse">
      <div className="flex justify-between items-center mb-4">
        <div className="h-3 bg-slate-200 dark:bg-slate-800 rounded w-24" />
        <div className="h-8 w-8 bg-slate-200 dark:bg-slate-800 rounded-lg" />
      </div>
      <div className="h-7 bg-slate-200 dark:bg-slate-800 rounded w-16 mb-2" />
      <div className="h-3 bg-slate-200 dark:bg-slate-800 rounded w-32" />
    </div>
  );
}

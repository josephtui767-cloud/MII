/** Pagination controls. */

interface PaginationProps {
  page: number;
  pages: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pages, onPageChange }: PaginationProps) {
  if (pages <= 1) return null;

  const range = (start: number, end: number) =>
    Array.from({ length: end - start + 1 }, (_, i) => start + i);

  // Show max 7 page buttons
  let pageNumbers: number[];
  if (pages <= 7) {
    pageNumbers = range(1, pages);
  } else if (page <= 4) {
    pageNumbers = [...range(1, 5), -1, pages];
  } else if (page >= pages - 3) {
    pageNumbers = [1, -1, ...range(pages - 4, pages)];
  } else {
    pageNumbers = [1, -1, page - 1, page, page + 1, -2, pages];
  }

  return (
    <nav className="flex items-center gap-1" aria-label="Pagination">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="px-3 py-1 text-sm rounded border border-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
      >
        Previous
      </button>

      {pageNumbers.map((num, idx) =>
        num < 0 ? (
          <span key={`ellipsis-${idx}`} className="px-2 text-gray-400">
            ...
          </span>
        ) : (
          <button
            key={num}
            onClick={() => onPageChange(num)}
            className={`px-3 py-1 text-sm rounded border ${
              num === page
                ? "bg-blue-600 text-white border-blue-600"
                : "border-gray-300 hover:bg-gray-50"
            }`}
          >
            {num}
          </button>
        )
      )}

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= pages}
        className="px-3 py-1 text-sm rounded border border-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
      >
        Next
      </button>
    </nav>
  );
}

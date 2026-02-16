import { useNavigate } from "react-router";

interface ListToggleButtonProps {
  bookId: number;
  isOnList: boolean;
  onAdd: (bookId: number) => void;
  onRemove: (bookId: number) => void;
  isAuthenticated: boolean;
}

export function ListToggleButton({
  bookId,
  isOnList,
  onAdd,
  onRemove,
  isAuthenticated,
}: ListToggleButtonProps) {
  const navigate = useNavigate();

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!isAuthenticated) {
      void navigate("/login");
      return;
    }

    if (isOnList) {
      onRemove(bookId);
    } else {
      onAdd(bookId);
    }
  };

  const label = isOnList ? "Remove from My List" : "Add to My List";

  return (
    <button
      type="button"
      onClick={handleClick}
      className="p-2.5 rounded-full bg-white/80 backdrop-blur-sm shadow-sm cursor-pointer transition-all hover:bg-white hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-leather"
      aria-label={label}
      title={label}
    >
      <svg
        className={`w-5 h-5 transition-colors ${
          isOnList
            ? "text-leather fill-leather"
            : "text-ink-light fill-none hover:text-leather"
        }`}
        viewBox="0 0 24 24"
        strokeWidth={1.5}
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z"
        />
      </svg>
    </button>
  );
}

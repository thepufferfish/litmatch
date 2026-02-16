import { useState, useEffect, useRef } from "react";
import { Link } from "react-router";
import type { UserPublic } from "@/types";

interface MobileNavProps {
  user: UserPublic | null;
  isAuthenticated: boolean;
  onLogout: () => void;
}

export function MobileNav({ user, isAuthenticated, onLogout }: MobileNavProps) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      // Prevent body scroll when menu is open
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  // Close on outside tap
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const closeMenu = () => setIsOpen(false);

  return (
    <div className="md:hidden" ref={menuRef}>
      {/* Hamburger menu button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 text-ink hover:text-leather transition-colors cursor-pointer"
        aria-label={isOpen ? "Close menu" : "Open menu"}
        aria-expanded={isOpen}
      >
        <svg
          className="w-6 h-6"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          {isOpen ? (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6 18 18 6M6 6l12 12"
            />
          ) : (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
            />
          )}
        </svg>
      </button>

      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-ink/20 z-40 transition-opacity"
          style={{ top: "var(--header-height, 68px)" }}
        />
      )}

      {/* Slide-in menu */}
      <div
        className={`fixed right-0 top-[var(--header-height,68px)] bottom-0 w-64 bg-cream border-l border-parchment shadow-xl z-50 transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <nav className="flex flex-col p-4 space-y-1">
          {isAuthenticated && user ? (
            <>
              {/* User info */}
              <div className="px-4 py-3 mb-2 rounded-lg bg-parchment">
                <span className="text-sm font-medium text-ink">{user.username}</span>
              </div>

              {/* Navigation links - min 44x44px touch targets */}
              <Link
                to="/profile"
                onClick={closeMenu}
                className="block px-4 py-3 rounded-lg text-base text-ink hover:bg-parchment transition-colors"
              >
                Recommended
              </Link>
              <Link
                to="/ratings"
                onClick={closeMenu}
                className="block px-4 py-3 rounded-lg text-base text-ink hover:bg-parchment transition-colors"
              >
                My Ratings
              </Link>
              <Link
                to="/list"
                onClick={closeMenu}
                className="block px-4 py-3 rounded-lg text-base text-ink hover:bg-parchment transition-colors"
              >
                My List
              </Link>

              {/* Divider */}
              <div className="border-t border-parchment my-2" />

              {/* Log out button */}
              <button
                onClick={() => {
                  onLogout();
                  closeMenu();
                }}
                className="block w-full text-left px-4 py-3 rounded-lg text-base text-muted hover:text-ink hover:bg-parchment transition-colors cursor-pointer"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              {/* Login/Register links */}
              <Link
                to="/login"
                onClick={closeMenu}
                className="block px-4 py-3 rounded-lg text-base text-ink hover:bg-parchment transition-colors"
              >
                Log in
              </Link>
              <Link
                to="/register"
                onClick={closeMenu}
                className="block px-4 py-3 rounded-lg text-base text-white bg-leather hover:bg-leather-light font-medium transition-colors"
              >
                Sign up
              </Link>
            </>
          )}
        </nav>
      </div>
    </div>
  );
}

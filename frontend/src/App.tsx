import { BrowserRouter, Routes, Route, Link } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { BrowsePage } from "@/pages/BrowsePage";
import { BookDetailPage } from "@/pages/BookDetailPage";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { ProfilePage } from "@/pages/ProfilePage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AuthButtons() {
  const { user, isAuthenticated, isLoading, logout } = useAuth();

  if (isLoading) {
    return <div className="w-20 h-8 skeleton-shimmer rounded" />;
  }

  if (isAuthenticated && user) {
    return (
      <div className="flex items-center gap-4">
        <Link
          to="/profile"
          className="text-sm text-ink-light hover:text-leather transition-colors"
        >
          Recommended
        </Link>
        <span className="text-sm text-ink-light">{user.username}</span>
        <button
          onClick={() => void logout()}
          className="text-sm text-muted hover:text-ink transition-colors cursor-pointer"
        >
          Log out
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <Link
        to="/login"
        className="text-sm text-ink-light hover:text-ink transition-colors"
      >
        Log in
      </Link>
      <Link
        to="/register"
        className="text-sm px-4 py-1.5 rounded-lg bg-leather text-white font-medium hover:bg-leather-light transition-colors"
      >
        Sign up
      </Link>
    </div>
  );
}

function Header() {
  return (
    <header className="sticky top-0 z-50 bg-cream/95 backdrop-blur-sm border-b border-parchment">
      <div className="max-w-[var(--container-max)] mx-auto px-6 py-4 flex items-center justify-between">
        <Link to="/" className="group flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-leather flex items-center justify-center">
            <svg
              className="w-5 h-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
              />
            </svg>
          </div>
          <span className="font-serif text-xl font-bold text-ink group-hover:text-leather transition-colors">
            LitMatch
          </span>
        </Link>
        <AuthButtons />
      </div>
    </header>
  );
}

function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-20 h-20 rounded-full bg-parchment flex items-center justify-center mb-6">
        <span className="font-serif text-3xl text-muted">404</span>
      </div>
      <h1 className="font-serif text-3xl text-ink mb-2">Page not found</h1>
      <p className="text-muted mb-6 max-w-md">
        The page you&apos;re looking for doesn&apos;t exist. It may have been
        moved or the URL might be incorrect.
      </p>
      <Link
        to="/"
        className="inline-flex items-center px-5 py-2.5 rounded-lg bg-leather text-white font-medium hover:bg-leather-light transition-colors"
      >
        Go to homepage
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <div className="min-h-screen bg-cream">
            <Header />
            <div className="max-w-[var(--container-max)] mx-auto px-6 py-8">
              <ErrorBoundary>
                <Routes>
                  <Route path="/" element={<BrowsePage />} />
                  <Route path="/genre/:slug" element={<BrowsePage />} />
                  <Route path="/books/:id" element={<BookDetailPage />} />
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/register" element={<RegisterPage />} />
                  <Route path="/profile" element={<ProfilePage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </ErrorBoundary>
            </div>
          </div>
          <Toaster
            position="bottom-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: "#2c1810",
                color: "#fdf9f0",
                fontFamily: "Inter, system-ui, sans-serif",
                fontSize: "14px",
                borderRadius: "10px",
              },
            }}
          />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

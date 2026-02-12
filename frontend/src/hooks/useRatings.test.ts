import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useUserRating, useUserRatingsMap, useSubmitRating, useDeleteRating } from "./useRatings";
import api from "@/api/client";
import type { Mock } from "vitest";
import type { UserRating } from "@/types";

// -- Mock API client ---------------------------------------------------------

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockGet = api.get as Mock;
const mockPost = api.post as Mock;
const mockDelete = api.delete as Mock;

// -- Test data ---------------------------------------------------------------

const mockRating: UserRating = {
  id: 1,
  user_id: 10,
  book_id: 42,
  rating: 4,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const mockRatings: UserRating[] = [
  mockRating,
  { ...mockRating, id: 2, book_id: 7, rating: 5 },
  { ...mockRating, id: 3, book_id: 15, rating: 2 },
];

// -- Helpers -----------------------------------------------------------------

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// -- Tests: useUserRating ----------------------------------------------------

describe("useUserRating", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches the user rating for a given book and user", async () => {
    mockGet.mockResolvedValue({ data: [mockRating] });

    const { result } = renderHook(() => useUserRating(42, 10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockRating);
    expect(mockGet).toHaveBeenCalledWith("/ratings/", {
      params: { book_id: 42 },
    });
  });

  it("returns null when the API returns an empty array", async () => {
    mockGet.mockResolvedValue({ data: [] });

    const { result } = renderHook(() => useUserRating(42, 10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toBeNull();
  });

  it("is disabled when userId is undefined", () => {
    const { result } = renderHook(() => useUserRating(42, undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("is disabled when bookId is 0 (falsy)", () => {
    const { result } = renderHook(() => useUserRating(0, 10), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });
});

// -- Tests: useUserRatingsMap ------------------------------------------------

describe("useUserRatingsMap", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches all user ratings and returns a Map", async () => {
    mockGet.mockResolvedValue({ data: mockRatings });

    const { result } = renderHook(() => useUserRatingsMap(10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const map = result.current.data!;
    expect(map).toBeInstanceOf(Map);
    expect(map.get(42)).toBe(4);
    expect(map.get(7)).toBe(5);
    expect(map.get(15)).toBe(2);
    expect(map.size).toBe(3);
  });

  it("returns empty Map when no ratings exist", async () => {
    mockGet.mockResolvedValue({ data: [] });

    const { result } = renderHook(() => useUserRatingsMap(10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data!.size).toBe(0);
  });

  it("is disabled when userId is undefined", () => {
    const { result } = renderHook(() => useUserRatingsMap(undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("calls GET /ratings/ without params", async () => {
    mockGet.mockResolvedValue({ data: [] });

    const { result } = renderHook(() => useUserRatingsMap(10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("/ratings/");
  });
});

// -- Tests: useSubmitRating --------------------------------------------------

describe("useSubmitRating", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits a rating via POST to /ratings/", async () => {
    const newRating: UserRating = {
      ...mockRating,
      rating: 5,
    };
    mockPost.mockResolvedValue({ data: newRating });

    const { result } = renderHook(() => useSubmitRating(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ book_id: 42, rating: 5 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockPost).toHaveBeenCalledWith("/ratings/", {
      book_id: 42,
      rating: 5,
    });
    expect(result.current.data).toEqual(newRating);
  });

  it("reports error when the API call fails", async () => {
    mockPost.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useSubmitRating(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ book_id: 42, rating: 3 });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toBe("Network error");
  });

  it("accepts optional userId parameter", async () => {
    const newRating: UserRating = { ...mockRating, rating: 5 };
    mockPost.mockResolvedValue({ data: newRating });

    const { result } = renderHook(() => useSubmitRating(10), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ book_id: 42, rating: 5 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockPost).toHaveBeenCalledWith("/ratings/", {
      book_id: 42,
      rating: 5,
    });
  });
});

// -- Tests: useDeleteRating --------------------------------------------------

describe("useDeleteRating", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("deletes a rating via DELETE /ratings/{bookId}", async () => {
    mockDelete.mockResolvedValue({});

    const { result } = renderHook(() => useDeleteRating(), {
      wrapper: createWrapper(),
    });

    result.current.mutate(42);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockDelete).toHaveBeenCalledWith("/ratings/42");
  });

  it("reports error when the API call fails", async () => {
    mockDelete.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useDeleteRating(), {
      wrapper: createWrapper(),
    });

    result.current.mutate(42);

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toBe("Network error");
  });

  it("accepts optional userId parameter", async () => {
    mockDelete.mockResolvedValue({});

    const { result } = renderHook(() => useDeleteRating(10), {
      wrapper: createWrapper(),
    });

    result.current.mutate(42);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockDelete).toHaveBeenCalledWith("/ratings/42");
  });
});

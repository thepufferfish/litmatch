import { useUserRating, useSubmitRating } from "./useRatings";

describe("useRatings hooks", () => {
  it("exports useUserRating function", () => {
    expect(typeof useUserRating).toBe("function");
  });

  it("exports useSubmitRating function", () => {
    expect(typeof useSubmitRating).toBe("function");
  });
});

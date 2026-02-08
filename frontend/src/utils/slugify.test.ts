import { slugify } from "./slugify";

describe("slugify", () => {
  it("lowercases the input", () => {
    expect(slugify("Fiction")).toBe("fiction");
  });

  it("replaces spaces with hyphens", () => {
    expect(slugify("literary fiction")).toBe("literary-fiction");
  });

  it("removes non-alphanumeric characters except hyphens", () => {
    expect(slugify("Science & Technology")).toBe("science-technology");
  });

  it("collapses consecutive hyphens", () => {
    expect(slugify("young   adult")).toBe("young-adult");
  });

  it("trims leading and trailing hyphens", () => {
    expect(slugify("  horror  ")).toBe("horror");
  });

  it("handles already-slugified input", () => {
    expect(slugify("literary-fiction")).toBe("literary-fiction");
  });

  it("handles empty string", () => {
    expect(slugify("")).toBe("");
  });

  it("handles string with only special characters", () => {
    expect(slugify("@#$%")).toBe("");
  });

  it("handles complex genre names", () => {
    expect(slugify("Children's Literature")).toBe("childrens-literature");
  });

  it("handles numbers in names", () => {
    expect(slugify("20th Century")).toBe("20th-century");
  });
});

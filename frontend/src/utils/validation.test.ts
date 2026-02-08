import { validateUsername, validatePassword } from "./validation";

describe("validateUsername", () => {
  it("returns null for valid username", () => {
    expect(validateUsername("valid_user1")).toBeNull();
  });

  it("returns null for 3-char username", () => {
    expect(validateUsername("abc")).toBeNull();
  });

  it("returns null for 30-char username", () => {
    expect(validateUsername("a".repeat(30))).toBeNull();
  });

  it("returns error for username shorter than 3 chars", () => {
    const result = validateUsername("ab");
    expect(result).not.toBeNull();
    expect(result).toContain("3");
  });

  it("returns error for username longer than 30 chars", () => {
    const result = validateUsername("a".repeat(31));
    expect(result).not.toBeNull();
    expect(result).toContain("30");
  });

  it("returns error for username with special characters", () => {
    expect(validateUsername("user@name")).not.toBeNull();
  });

  it("returns error for username with spaces", () => {
    expect(validateUsername("user name")).not.toBeNull();
  });

  it("allows underscores in username", () => {
    expect(validateUsername("user_name_123")).toBeNull();
  });

  it("returns error for empty username", () => {
    expect(validateUsername("")).not.toBeNull();
  });
});

describe("validatePassword", () => {
  it("returns null for valid password", () => {
    expect(validatePassword("Secret123")).toBeNull();
  });

  it("returns null for minimum valid password", () => {
    expect(validatePassword("Abcdefg1")).toBeNull();
  });

  it("returns error for password shorter than 8 chars", () => {
    const result = validatePassword("Abc1");
    expect(result).not.toBeNull();
    expect(result).toContain("8");
  });

  it("returns error for password without digit", () => {
    const result = validatePassword("NoDigitsHere");
    expect(result).not.toBeNull();
    expect(result).toContain("digit");
  });

  it("returns error for password without letter", () => {
    const result = validatePassword("12345678");
    expect(result).not.toBeNull();
    expect(result).toContain("letter");
  });

  it("returns error for password longer than 72 chars", () => {
    // 73 characters (exceeds bcrypt's 72-byte limit)
    const longPassword = "A1" + "x".repeat(71);
    const result = validatePassword(longPassword);
    expect(result).not.toBeNull();
    expect(result).toContain("72");
  });

  it("returns null for password at maximum length", () => {
    // Exactly 72 characters (bcrypt's limit)
    const maxPassword = "A1" + "x".repeat(70);
    expect(validatePassword(maxPassword)).toBeNull();
  });

  it("returns error for empty password", () => {
    expect(validatePassword("")).not.toBeNull();
  });
});

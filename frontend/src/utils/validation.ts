const USERNAME_PATTERN = /^[a-zA-Z0-9_]{3,30}$/;

export function validateUsername(username: string): string | null {
  if (username.length < 3) {
    return "Username must be 3-30 characters";
  }
  if (username.length > 30) {
    return "Username must be 3-30 characters";
  }
  if (!USERNAME_PATTERN.test(username)) {
    return "Username can only contain letters, numbers, and underscores";
  }
  return null;
}

export function validatePassword(password: string): string | null {
  if (password.length < 8) {
    return "Password must be at least 8 characters";
  }
  if (password.length > 72) {
    return "Password must not exceed 72 characters";
  }
  if (!/[a-zA-Z]/.test(password)) {
    return "Password must contain at least one letter";
  }
  if (!/[0-9]/.test(password)) {
    return "Password must contain at least one digit";
  }
  return null;
}

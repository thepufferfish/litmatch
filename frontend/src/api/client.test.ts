/// <reference types="node" />
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect, beforeEach } from "vitest";

/**
 * Tests for the API client module.
 *
 * Bug 1 regression: The `attemptTokenRefresh` function previously used bare
 * `axios.post("/api/auth/refresh")` which bypasses the Vite proxy in production,
 * causing a 404. It must use the configured `api` instance instead.
 */

const currentDir = dirname(fileURLToPath(import.meta.url));

describe("API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("module exports", () => {
    it("exports default api instance", async () => {
      const clientModule = await import("@/api/client");
      expect(clientModule.default).toBeDefined();
    });

    it("exports setAuthHelpers function", async () => {
      const { setAuthHelpers } = await import("@/api/client");
      expect(typeof setAuthHelpers).toBe("function");
    });
  });

  describe("api instance configuration", () => {
    it("has baseURL set to /api", async () => {
      const { default: api } = await import("@/api/client");
      expect(api.defaults.baseURL).toBe("/api");
    });

    it("has withCredentials enabled", async () => {
      const { default: api } = await import("@/api/client");
      expect(api.defaults.withCredentials).toBe(true);
    });

    it("has Content-Type header set to application/json", async () => {
      const { default: api } = await import("@/api/client");
      expect(api.defaults.headers["Content-Type"]).toBe("application/json");
    });
  });

  describe("token refresh uses api client (Bug 1 regression)", () => {
    /**
     * Helper to strip comments from source code so we only test executable lines.
     * Removes multi-line comments and single-line comments (preserving URLs).
     */
    function stripComments(source: string): string {
      let result = source.replace(/\/\*[\s\S]*?\*\//g, "");
      result = result
        .split("\n")
        .map((line) => line.replace(/(?<!\w:)\/\/.*$/, ""))
        .join("\n");
      return result;
    }

    it("attemptTokenRefresh must NOT use bare axios.post for the refresh call", () => {
      // Read the source file and check code-only lines (excluding comments).
      //
      // Bare axios.post bypasses:
      //  - The configured baseURL ("/api")
      //  - Request interceptors (Authorization header injection)
      //  - Response interceptors (error handling)
      //  - Vite proxy in production (causing 404 on POST /api/auth/refresh)
      const sourcePath = resolve(currentDir, "client.ts");
      const source = readFileSync(sourcePath, "utf-8");
      const codeOnly = stripComments(source);

      const usesBareAxiosForRefresh =
        /axios\.post\(\s*["']\/api\/auth\/refresh["']/.test(codeOnly);

      expect(usesBareAxiosForRefresh).toBe(false);
    });

    it("attemptTokenRefresh must use api.post for the refresh call", () => {
      const sourcePath = resolve(currentDir, "client.ts");
      const source = readFileSync(sourcePath, "utf-8");
      const codeOnly = stripComments(source);

      const usesApiClientForRefresh =
        /api\.post[<(][\s\S]*?["']\/auth\/refresh["']/.test(codeOnly);

      expect(usesApiClientForRefresh).toBe(true);
    });
  });
});

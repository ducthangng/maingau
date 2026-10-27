import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

// `npm test`: unit and render tests next to the code (src/**/*.test.ts[x]); Node environment,
// components are rendered with react-dom/server.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: { environment: "node", include: ["src/**/*.test.{ts,tsx}"] },
  }),
);

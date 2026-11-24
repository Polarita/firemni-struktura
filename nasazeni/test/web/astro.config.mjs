import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/web-test",
  output: "static",
  trailingSlash: "always",
  build: { inlineStylesheets: "always" },
  vite: { plugins: [tailwindcss()] }
});

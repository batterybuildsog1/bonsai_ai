import { defineConfig } from "vite";
import { resolve } from "node:path";
import { existsSync, readFileSync, readdirSync, statSync, copyFileSync, mkdirSync } from "node:fs";

const PROJECT_ROOT = resolve(import.meta.dirname, "..");

export default defineConfig({
  server: {
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "require-corp",
    },
    fs: {
      allow: [PROJECT_ROOT, resolve(import.meta.dirname)],
    },
  },
  preview: {
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "require-corp",
    },
  },
  worker: {
    format: "es",
  },
  plugins: [
    {
      // Fix @ifc-lite/geometry referencing geometry.worker.ts (TypeScript source)
      // in new URL() calls — only the compiled .js exists in the dist.
      // Vite special-cases `new URL(path, import.meta.url)` before normal resolution,
      // so we need to rewrite the source code directly.
      name: "fix-ifc-lite-worker-url",
      enforce: "pre",
      transform(code, id) {
        if (id.includes("@ifc-lite/geometry") && code.includes("geometry.worker.ts")) {
          return {
            code: code.replaceAll("geometry.worker.ts", "geometry.worker.js"),
            map: null,
          };
        }
      },
    },
    {
      name: "serve-out-dir",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (!req.url?.startsWith("/out/")) return next();

          const filePath = resolve(PROJECT_ROOT, req.url.slice(1));
          if (!existsSync(filePath)) {
            res.statusCode = 404;
            res.end("Not found");
            return;
          }

          const stat = statSync(filePath);
          if (stat.isDirectory()) {
            const entries = readdirSync(filePath);
            res.setHeader("Content-Type", "application/json");
            res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
            res.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
            res.end(JSON.stringify(entries));
            return;
          }

          const ext = filePath.split(".").pop()?.toLowerCase();
          const mimeTypes = {
            ifc: "application/octet-stream",
            json: "application/json",
            blend: "application/octet-stream",
            md: "text/markdown",
            wasm: "application/wasm",
          };

          res.setHeader("Content-Type", mimeTypes[ext] || "application/octet-stream");
          res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
          res.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
          res.end(readFileSync(filePath));
        });
      },
    },
  ],
  build: {
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, "index.html"),
        benchmark: resolve(import.meta.dirname, "benchmark.html"),
      },
    },
  },
  optimizeDeps: {
    exclude: ["@ifc-lite/wasm"],
  },
  assetsInclude: ["**/*.wasm", "**/*.ifc"],
});

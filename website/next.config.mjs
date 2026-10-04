import { fileURLToPath } from "node:url";

/** Static export: deployable to Vercel, Netlify or any static host. No server runtime, no secrets. */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
  // Pin the workspace root to this directory (avoids picking up unrelated lockfiles).
  outputFileTracingRoot: fileURLToPath(new URL(".", import.meta.url)),
  eslint: { ignoreDuringBuilds: true }, // type checking runs in `next build`; lint is not configured
};

export default nextConfig;

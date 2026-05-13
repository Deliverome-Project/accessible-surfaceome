import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  // Pin file-tracing root to this directory so Next stops warning
  // about the parent-repo lockfile. The viewer is its own Pages
  // project; nothing here needs to trace back into the Python tree.
  outputFileTracingRoot: __dirname,
};

export default nextConfig;

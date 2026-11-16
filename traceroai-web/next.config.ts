import createMDX from "@next/mdx";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {};

// Docs pages are MDX files in src/content/docs, loaded by app/docs/[[...slug]].
// Plugins are named as strings so they work with Turbopack.
const withMDX = createMDX({
  options: {
    remarkPlugins: ["remark-gfm"], // tables
    rehypePlugins: ["rehype-slug"], // heading ids, for "On this page" and links
  },
});

export default withMDX(nextConfig);

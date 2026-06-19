import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/docs"],
        disallow: ["/dashboard/traces/", "/dashboard/eval-runs/"],
      },
    ],
    sitemap: "https://www.traceroai.tech/sitemap.xml",
  };
}

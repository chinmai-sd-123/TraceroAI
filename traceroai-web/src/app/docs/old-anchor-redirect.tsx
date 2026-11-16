"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { OLD_ANCHORS, docHref } from "@/lib/docs-nav";

/** The docs used to be one page; /docs#config and the like now have pages of
 * their own. A link to an old section lands on its new page. */
export function OldAnchorRedirect() {
  const router = useRouter();
  useEffect(() => {
    const target = OLD_ANCHORS[window.location.hash.slice(1)];
    if (target !== undefined) router.replace(docHref(target));
  }, [router]);
  return null;
}

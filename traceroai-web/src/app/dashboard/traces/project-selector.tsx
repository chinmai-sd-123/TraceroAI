"use client";

import { useRouter } from "next/navigation";

export function ProjectSelector({
  projects,
  selected,
  basePath = "/dashboard/traces",
}: {
  projects: string[];
  selected?: string;
  // Where to navigate on change. Both the Overview and Traces pages use this
  // selector; each passes its own path so the filter stays on the current page.
  basePath?: string;
}) {
  const router = useRouter();

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-3">
      <label className="block text-xs text-zinc-500">Project</label>
      <select
        value={selected ?? ""}
        onChange={(event) => {
          const value = event.target.value;
          router.push(value ? `${basePath}?project=${encodeURIComponent(value)}` : basePath);
        }}
        className="mt-1 bg-transparent text-sm font-medium text-zinc-100 focus:outline-none"
      >
        <option value="" className="bg-zinc-900">
          All projects
        </option>
        {projects.map((project) => (
          <option key={project} value={project} className="bg-zinc-900">
            {project}
          </option>
        ))}
      </select>
    </div>
  );
}

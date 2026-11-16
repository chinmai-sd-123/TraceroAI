import type { ReactNode, SVGProps } from "react";

// The dashboard's icons: 16px, 1.5px stroke, round joins, drawn on a 16-unit
// grid so they sit on the text baseline at 14px type.

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 16, children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export const OverviewIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M2.5 13.5h11" />
    <path d="M4.5 11V8" />
    <path d="M8 11V4.5" />
    <path d="M11.5 11V6.5" />
  </Icon>
);

/** Three linked stages: the trace list. */
export const TracesIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="1.75" y="6" width="3.5" height="4" rx="0.75" />
    <rect x="6.25" y="6" width="3.5" height="4" rx="0.75" />
    <rect x="10.75" y="6" width="3.5" height="4" rx="0.75" />
  </Icon>
);

/** A loop back on itself: the RecoveryAgent retrying. */
export const RecoveryIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M13 8a5 5 0 1 1-1.46-3.54" />
    <path d="M13 2.5v3h-3" />
  </Icon>
);

export const EvalRunsIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 2.5h4" />
    <path d="M6.75 2.5v4L3.2 12.4A.75.75 0 0 0 3.85 13.5h8.3a.75.75 0 0 0 .65-1.1L9.25 6.5v-4" />
    <path d="M4.6 10h6.8" />
  </Icon>
);

export const DocsIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3.5 2.5h6l3 3v8h-9z" />
    <path d="M9.5 2.5v3h3" />
    <path d="M5.5 8.5h5M5.5 11h3.5" />
  </Icon>
);

export const CodeIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5.5 4.5 2 8l3.5 3.5" />
    <path d="M10.5 4.5 14 8l-3.5 3.5" />
  </Icon>
);

export const SearchIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="7" cy="7" r="4.25" />
    <path d="m10.25 10.25 3.25 3.25" />
  </Icon>
);

export const CopyIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="5.25" y="5.25" width="8" height="8" rx="1.25" />
    <path d="M10.75 5.25V3.5a.75.75 0 0 0-.75-.75H3.5a.75.75 0 0 0-.75.75V10c0 .41.34.75.75.75h1.75" />
  </Icon>
);

export const CheckIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m3 8.5 3 3 7-7" />
  </Icon>
);

export const CrossIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m4 4 8 8M12 4l-8 8" />
  </Icon>
);

export const ArrowLeftIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M13 8H3" />
    <path d="M7 4 3 8l4 4" />
  </Icon>
);

export const ArrowRightIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 8h10" />
    <path d="M9 4l4 4-4 4" />
  </Icon>
);

export const ThumbUpIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 7v6.5H2.75V7z" />
    <path d="M5 7l2.6-4.5a1.3 1.3 0 0 1 2.4.85L9.5 6h3.2a1.25 1.25 0 0 1 1.22 1.52l-1.1 5A1.25 1.25 0 0 1 11.6 13.5H5" />
  </Icon>
);

export const ThumbDownIcon = (p: IconProps) => (
  <Icon {...p} style={{ transform: "scaleY(-1)", ...p.style }}>
    <path d="M5 7v6.5H2.75V7z" />
    <path d="M5 7l2.6-4.5a1.3 1.3 0 0 1 2.4.85L9.5 6h3.2a1.25 1.25 0 0 1 1.22 1.52l-1.1 5A1.25 1.25 0 0 1 11.6 13.5H5" />
  </Icon>
);

export const AlertIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M7.13 2.6a1 1 0 0 1 1.74 0l5.4 9.4a1 1 0 0 1-.87 1.5H2.6a1 1 0 0 1-.87-1.5z" />
    <path d="M8 6.5v2.75" />
    <path d="M8 11.25h.01" />
  </Icon>
);

/** A panel with its left rail: collapse or expand the sidebar. */
export const SidebarIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="2" y="2.75" width="12" height="10.5" rx="1.5" />
    <path d="M6 2.75v10.5" />
  </Icon>
);

export const SignOutIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 2.75H3.5a.75.75 0 0 0-.75.75v9c0 .41.34.75.75.75H6" />
    <path d="M10 5l3 3-3 3" />
    <path d="M13 8H6" />
  </Icon>
);

/** Panels of different widths: customize the layout. */
export const LayoutIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="2" y="2.5" width="7" height="5" rx="1" />
    <rect x="10.5" y="2.5" width="3.5" height="5" rx="1" />
    <rect x="2" y="9" width="12" height="4.5" rx="1" />
  </Icon>
);

export const HideIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M2 8s2.25-4.25 6-4.25S14 8 14 8s-2.25 4.25-6 4.25S2 8 2 8z" />
    <circle cx="8" cy="8" r="1.75" />
    <path d="M3 13 13 3" />
  </Icon>
);

export const PlusIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M8 3v10M3 8h10" />
  </Icon>
);

export const ChevronLeftIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10 3.5 5.5 8l4.5 4.5" />
  </Icon>
);

/** Stacked sheets with a mark: failures grouped into issues. */
export const IssuesIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="2.5" y="5" width="9" height="8.5" rx="1" />
    <path d="M5 2.5h7.5a1 1 0 0 1 1 1V11" />
    <path d="M7 7.5v2.25" />
    <path d="M7 11.75h.01" />
  </Icon>
);

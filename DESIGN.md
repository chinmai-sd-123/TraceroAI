---
name: TraceroAI
description: TraceroAI's visual system, for the dashboard, the home page and the docs. Every bad answer reads as an incident report.
colors:
  docket-navy: "#1d3a5f"
  docket-navy-soft: "#e3e9f1"
  cause-red: "#b42318"
  cause-red-soft: "#fdecea"
  pass-green: "#1d7348"
  pass-green-soft: "#e6f2ec"
  unclear-amber: "#95500a"
  unclear-amber-soft: "#fbf0e1"
  report-white: "#ffffff"
  docket-rail: "#eef2f6"
  sunken: "#f4f6f9"
  rule: "#dfe4ea"
  rule-strong: "#c5ccd6"
  ink: "#14202e"
  ink-muted: "#4f5a6b"
  ink-faint: "#687284"
typography:
  headline:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.33
    letterSpacing: "-0.015em"
  verdict:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.4
  title:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.5
  body:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  label:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.33
  data:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  mark: "3px"
  control: "4px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.docket-navy}"
    textColor: "{colors.report-white}"
    rounded: "{rounded.control}"
    padding: "6px 14px"
  button-secondary:
    backgroundColor: "{colors.report-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "6px 14px"
  nav-item-active:
    backgroundColor: "{colors.docket-navy}"
    textColor: "{colors.report-white}"
    rounded: "{rounded.control}"
    padding: "6px 8px"
  chip-filter-active:
    backgroundColor: "{colors.docket-navy-soft}"
    textColor: "{colors.docket-navy}"
    rounded: "{rounded.control}"
    padding: "4px 10px"
  badge-cause:
    backgroundColor: "{colors.cause-red-soft}"
    textColor: "{colors.cause-red}"
    rounded: "{rounded.control}"
    padding: "1px 6px"
  input-text:
    backgroundColor: "{colors.report-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "6px 10px"
---

# Design System: TraceroAI

## Overview

**Creative North Star: "The Investigation Docket"**

The dashboard treats every bad answer as an incident to investigate. A trace reads like an accident report: what happened, in sequence (Retrieval, Grounding, Answer), the findings for each stage, and one probable cause. The visual system borrows the report's materials and leaves its bureaucracy behind: white report stock for the work, a pale blue-grey docket rail around it, 1px rules for structure, and a typeface drawn for government reports.

Density is that of a working tool used for long investigations. Lists are compact. Evidence (judge reasons, retrieved chunks, claims) gets reading width and line height, because the engineer reads it rather than scans it. The shell follows the category's conventions: a left rail with grouped navigation, page headers with a time range, ruled metric rows and charts. The report world shows up in type, palette, rules and one signature component, the stage sequence. It never changes the layout or the controls.

How sure we are is drawn rather than coloured. A verdict the LLM judge made is solid and called Final. One an estimate made (term overlap, embedding similarity) is hatched and called Preliminary. When the judge overrules an estimate, the estimate stays on the record, struck through.

The home page and the docs use the same system. The home page reads as a short technical report on TraceroAI, with a contents rail, and it moves: but every animation acts out what the product does to a real trace (a stage is checked, a verdict stamps in, the judge overrules an estimate), using real data from the example app. Nothing moves for decoration.

**Key Characteristics:**
- White work areas on a tinted docket rail; structure from 1px rules, never shadows.
- Red marks the probable cause and nothing else.
- Solid means judged, hatched means estimated.
- Public Sans for words, IBM Plex Mono for ids, sources, scores and code.
- Standard web controls throughout: tables, underline tabs, segmented links, selects.

## Colors

A cool, institutional palette: one navy for everything interactive, and status colours that each keep a single meaning.

### Primary
- **Docket Navy** (`docket-navy`): the selected nav item, primary buttons, the active tab's underline, links, focus outlines, the selected time range, and the latency line. The tinted version (`docket-navy-soft`) backs selected rows and active filter chips.

### Secondary
- **Cause Red** (`cause-red`, soft `cause-red-soft`): the probable cause. It colours the failing diagnosis name and badge, the blamed stage's column and bar in the stage sequence, and an unsupported claim when grounding is the cause.
- **Pass Green** (`pass-green`, soft `pass-green-soft`): passed stages, healthy diagnoses, the recommended experiment variant, and confirmations ("Feedback saved", "Copied").
- **Unclear Amber** (`unclear-amber`, soft `unclear-amber-soft`): "needs review", unclear stages, and every error or warning in the interface (API banners, form errors, failed runs), so red never has to mean a system problem.

### Neutral
- **Report White** (`report-white`): page and panel background.
- **Docket Rail** (`docket-rail`): the sidebar and the login backdrop.
- **Sunken** (`sunken`): table headers, row hover, code and JSON blocks, the list beside an open trace.
- **Rule** and **Rule Strong** (`rule`, `rule-strong`): dividers and panel borders; the strong rule frames inputs, the stage docket and table heads.
- **Ink**, **Ink Muted**, **Ink Faint**: body text, secondary text and labels, placeholders and stage numbers. A failed stage that is not the cause is drawn in Ink Muted.

### Named Rules
**The One Red Rule.** Red appears only on the probable cause. A second failing stage is ink; an error message is amber; a failed eval case says "Failed" in ink. If something red is not the reason an answer went wrong, it is the wrong colour. The one deliberate exception is the reviewer's stroke drawn under "failed." in the home page headline.

**The Drawn Certainty Rule.** Certainty is shown by fill, not by another colour: solid for the LLM judge, a 135° hatch (2px line, 4.5px repeat, in the element's own colour) for estimates. Every verdict on screen is one or the other.

## Typography

**Body Font:** Public Sans (fallback ui-sans-serif, system-ui)
**Data Font:** IBM Plex Mono, 400 and 500

**Character:** Public Sans was drawn for US government documents: neutral, legible at small sizes, slightly formal. That suits a report. Plex Mono is used only for things that are literally data (trace ids, chunk sources, scores, config values, code), never as decoration.

### Hierarchy
- **Headline** (600, 1.5rem, -0.015em): page titles and the question at the top of a trace. Balanced wrapping.
- **Verdict** (600, 1.25rem): the diagnosis name on the trace page, coloured by its tone.
- **Title** (600, 1rem): panel headings and stage names.
- **Body** (400, 0.875rem, tabular figures): tables, lists, reasons. Evidence prose (the diagnosis reason, an answer, chunk text) runs at 15px with 1.75 line height and a 70 to 75ch measure.
- **Label** (500, 0.75rem): field labels, legends, chart axes, provenance marks.
- **Data** (Plex Mono 400, 0.8125rem): ids, sources, scores, config values.

### Named Rules
**The No Eyebrow Rule.** Headings carry their own weight. No labels, pills or uppercase lines above headings, and no tracked-out caps anywhere. A sentence of context goes below the heading.

**Display** (700, clamp(2.4rem, 5.2vw, 4.4rem), -0.035em): the home page headline only. Section headings on the public pages are 700 at 1.75rem.

## Layout

The shell is a 14rem docket rail beside the work area from the `lg` breakpoint (1024px); below it the rail collapses into a top bar with the project select and a horizontally scrolling nav. From `lg` the rail can collapse to a 4rem strip of icons (labels move to tooltips and `aria-label`s). One round toggle straddles the rail's right edge near the top, in the same place open or collapsed, and `[` does the same; the column width eases over 200ms. Ordinary pages sit in a 76rem container with 16px side gutters on phones and 32px from `sm` up.

The trace page runs full bleed: a list of traces (19rem by default, sticky, scrolling on its own) beside the investigation, which caps at 68rem. The list and the execution timeline can be resized by dragging the 1px rule on their right edge (or with the arrow keys on it; Enter or a double-click resets). The list keeps the filters it was opened with, so the engineer can step through a filtered set without losing their place. Below `lg` the list is hidden and a back link leads to the full table.

Spacing follows a 4px base: 8px inside controls, 16px between related items, 24px between panels and sections. The overview uses a 12-column grid at `lg`; each panel spans 4, 6, 8 or 12 columns. The traces table becomes two-line rows below `md` (768px) rather than scrolling sideways.

### Customizable layout

The viewer's layout lives in one cookie (`traceroai_layout`), so the server renders it at their sizes from the first frame; nothing about it is stored server-side.

- **Overview:** "Customize layout" (beside the time range) turns on a toolbar joined to the top of each panel: a drag handle, a width control (⅓, ½, ⅔, Full), move earlier and later, and hide. A tinted bar above the grid explains the controls, lists hidden panels to show again, and holds "Reset layout". Done or Esc ends editing. The metric row stays fixed.
- **Rows are always full.** Panels fill rows in order; when the next panel doesn't fit, the last panel on the row widens to close the gap and says "Widened to fill the row" while editing. Panels on a row share its height.
- Changes animate with a 240ms view transition where the browser supports it; snapshots are clipped, never stretched. Reduced motion makes them instant.
- Below `lg` every panel is full width and the controls are hidden.

## Elevation & Depth

The system is flat. There are no shadows. Depth comes from tone (white work on the tinted rail, sunken table heads and code blocks) and from 1px rules. Panels are bordered, not lifted.

### Named Rules
**The Ruled Page Rule.** Structure is drawn with 1px lines in `rule` or `rule-strong`. A container that needs to stand apart gets a border, never a shadow or a coloured side stripe.

## Shapes

Corners are nearly square: 4px on panels, inputs, buttons, chips and nav items; 3px on small marks (provenance marks, the "Probable cause" tag, status pills). Bars in charts and the stage sequence are square-ended. The only accent stripe is the 3px bar across the top of each stage column, which carries the stage's verdict colour and fill.

## Components

### Buttons
Plain and restrained.
- **Primary:** navy fill, white text, 4px corners, 6px by 14px. Hover lightens the fill to 90%. Disabled drops to 60% opacity with a not-allowed cursor.
- **Secondary:** white with a strong-rule border and ink text; hover fills with `sunken`.
- **Copy button:** secondary style at 12px. On click the copy icon swaps for a green check and the label reads "Copied" for two seconds (200ms ease-out scale and fade).

### Chips
- **Filter chips:** white with a strong-rule border, the count in muted ink. The active chip takes the navy tint, navy border and navy text.
- **Diagnosis badges:** soft fill in the diagnosis tone (red for a cause, green healthy, amber needs review) with 600-weight text.

### Cards / Containers
- **Panels:** white, 1px `rule` border, 4px corners, 20px padding; a heading row (title, optional description, optional action link) over the content. Tables and lists inside a panel run edge to edge.
- **Metric row:** one bordered band divided by vertical rules: label, value (1.5rem, 600), detail line, and a small bar chart of the value's recent history.

### Inputs / Fields
- **Style:** white, strong-rule border, 4px corners, a muted 16px icon at the left of search fields.
- **Focus:** a 2px navy outline (`:focus-visible` across the dashboard, offset 2px).
- **Error:** amber message below the field, linked with `aria-describedby`.

### Navigation
- **Rail:** wordmark, project select, an "Open a trace by id" field, then grouped items with 16px icons (1.5px stroke). The active item is a solid navy block with white text and icon; hover is white on the rail.
- **Tabs:** underline tabs as links (each tab has a URL). Active is a 2px navy underline and 600 weight; on phones the row scrolls and fades at the right edge.
- **Time range:** segmented links (24h, 7d, 30d, All); the active segment is solid navy.

### Stage Sequence (signature component)
Three segments in pipeline order: Retrieval, Grounding, Answer. In lists each segment is a 20px by 8px bar; on the trace page it becomes the stage docket, three ruled columns, each with its number, name, verdict word, the question its check asks, the reason given, and who decided it ("Final: decided by the LLM judge" or "Preliminary: estimated from term overlap"). The blamed stage's column takes the soft red ground and a "Probable cause" tag. Segment colour: red for the cause, ink muted for another failure, green for passed, amber for unclear, strong rule for not checked. Fill: solid when judged, hatched when estimated. Every sequence carries a text label for screen readers.

### Code block
The one dark element: ink (`#14202e`) ground, light text, Plex Mono at 13px, comments, strings and keywords lightly tinted. Tabs above when there's more than one snippet (arrow keys move between them), and a copy button in its dark variant.

### Contents rail (public pages)
The home page and docs list their sections in a sticky rail. A navy-tinted highlight glides to the section being read; each item has a small marker, hollow ahead, solid navy once passed, ringed while current.

### Provenance Mark
A small bordered mark next to every diagnosis: a solid ink border reading "Final · LLM judge", or a dashed border reading "Preliminary · term-overlap estimate" (plus "judge pending" or "judge failed" when that applies). In tables it shows the word alone, with the method in the tooltip and screen-reader text.

### Motion (public pages)
One family of moves, all from the product's vocabulary, eased out (`cubic-bezier(0.16, 1, 0.3, 1)`), and every one settles to its finished state under reduced motion:
- **Investigation replay** (home hero): a real trace plays through question, typed answer, each stage scanned and stamped, the estimate struck as the judge takes over, then the probable cause and recovery run. Cycles three real cases; pausable.
- **Anatomy of a diagnosis**: a pinned, scroll-driven walk through one real trace, from retrieval to the judge checking each claim, to the red and green stamps. On phones it shows the finished trace.
- **Trace stream**: rows of stage-sequence marks drifting past on a canvas; they slow and lift under the pointer, and hovering one names it.
- **Trace record backdrop**: the hero's background is a real stored trace in faint 11px mono; the cursor brings it into focus in navy.
- **Reveals**: figures wipe up into view once; headings wipe in with scroll-driven CSS where supported; numbers count up once.
- **Footer wordmark**: "TraceroAI" at 21vw in translucent navy fading to nothing.

## Do's and Don'ts

### Do:
- **Do** keep red for the probable cause (The One Red Rule); errors and warnings are amber.
- **Do** draw every verdict solid or hatched by who decided it (The Drawn Certainty Rule).
- **Do** show "—", "No score" or "Not measured" for missing values; never a zero that was not measured.
- **Do** use Plex Mono only for ids, sources, scores, config and code.
- **Do** keep evidence prose at a 70 to 75ch measure with generous line height.
- **Do** make filters, tabs and pages URLs, so every view can be linked to and works without JavaScript.
- **Do** animate only what the product does, with its real data, and give every animation a finished state for reduced motion.

### Don't:
- **Don't** add shadows, floating cards or coloured side stripes; use 1px rules (The Ruled Page Rule).
- **Don't** put uppercase eyebrow labels above headings (The No Eyebrow Rule).
- **Don't** use emoji or text glyphs as icons; icons are 16px SVG at a 1.5px stroke.
- **Don't** reintroduce the old dark theme or a single cyan accent; the product is light by decision.
- **Don't** use decorative grid-line or gradient-orb backgrounds; texture comes from the product's own material (the trace record, the stage marks).
- **Don't** let the report world reach the controls: tables, tabs, buttons and selects stay standard web components.

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
  light-table: "#ffffff"
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

The home page and the docs use the same system. The home page follows one real failed run from the example app (trace 5f7bf901) from top to bottom: its case file opens in the hero, its trace folds into a verdict, it is taken apart on the light table, and a red thread ties those chapters to the recovery run that fixed it. Every animation acts out what the product does to that run, with its real data. Nothing moves for decoration.

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
- **Docket Rail** (`docket-rail`): the sidebar, the login backdrop, and the room the home page's light table stands in.
- **Light Table** (`light-table`): pure white on the rail tint, so the table reads as lit from below. Used by the light table only.
- **Sunken** (`sunken`): table headers, row hover, code and JSON blocks, the list beside an open trace.
- **Rule** and **Rule Strong** (`rule`, `rule-strong`): dividers and panel borders; the strong rule frames inputs, the stage docket and table heads.
- **Ink**, **Ink Muted**, **Ink Faint**: body text, secondary text and labels, placeholders and stage numbers. A failed stage that is not the cause is drawn in Ink Muted.

### Named Rules
**The One Red Rule.** Red appears only on the probable cause. A second failing stage is ink; an error message is amber; a failed eval case says "Failed" in ink. If something red is not the reason an answer went wrong, it is the wrong colour. Two marks on the home page belong to the same rule: the reviewer's stroke under "broke." in the headline, and the red thread, which is the cause's trail through the page.

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

**Display** (700, clamp(2.75rem, 6.4vw, 4.75rem), -0.042em, set 0.04em into the margin so the glyphs align optically): the home page headline only. Section headings on the home page are 700 at 2.5rem (-0.03em); in the docs, 1.75rem.

## Layout

The home page alternates white and the rail tint by act: white for the hero and the explanation, the tint for the light table, white again, and the tint for the closing band ("Run it yourself"), which repeats the headline and runs into the footer. The trace printout sits only on the hero's right side, behind the case file, so the headline is on calm paper; below 1280px it's hidden.

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

The system is flat. Depth comes from tone (white work on the tinted rail, sunken table heads and code blocks) and from 1px rules. Panels are bordered, not lifted.

The one exception is **paper lying on a surface**: the `.sheet` elevation (a hairline plus one soft contact shadow) on the home page's case file, the light table's sheets, and the header's panels, which float over the page. Nothing else casts a shadow.

**Translucency, only over content.** Frosted glass is used where something sits on top of other content, and nowhere else: the site header (`.glass-bar`, its frosting on a layer behind it so its panels can blur the page), the header's panels (`.glass-strong`), the hero case file over the trace printout (`.glass-card`, blurred hard enough that text behind it is only a haze), and the light table's sheets, which are acetates (`.acetate`): each shows the layers beneath it, softened. Every one has an opaque fallback where `backdrop-filter` isn't supported.

### Named Rules
**The Ruled Page Rule.** Structure is drawn with 1px lines in `rule` or `rule-strong`. A container that needs to stand apart gets a border, never a shadow or a coloured side stripe (paper on a surface excepted, above).

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
- **Site header (public pages):** Product, Docs and Open source each open a panel on hover (after a short pause, so passing over doesn't open it), on click, or with ArrowDown. A panel is a grid of links, each with a title and one line on what's behind it; Product's panel adds the home page's case. Esc closes and returns focus; moving between items switches panels at once. It's a disclosure (button and links), not an ARIA menu. On phones one Menu button lists all three groups.

### Stage Sequence (signature component)
Three segments in pipeline order: Retrieval, Grounding, Answer. In lists each segment is a 20px by 8px bar; on the trace page it becomes the stage docket, three ruled columns, each with its number, name, verdict word, the question its check asks, the reason given, and who decided it ("Final: decided by the LLM judge" or "Preliminary: estimated from term overlap"). The blamed stage's column takes the soft red ground and a "Probable cause" tag. Segment colour: red for the cause, ink muted for another failure, green for passed, amber for unclear, strong rule for not checked. Fill: solid when judged, hatched when estimated. Every sequence carries a text label for screen readers.

### Code block
The one dark element: ink (`#14202e`) ground, light text, Plex Mono at 13px, comments, strings and keywords lightly tinted. Tabs above when there's more than one snippet (arrow keys move between them), and a copy button in its dark variant.

### Contents rail (public pages)
The docs list a page's sections in a sticky rail. A navy-tinted highlight glides to the section being read; each item has a small marker, hollow ahead, solid navy once passed, ringed while current.

### Provenance Mark
A small bordered mark next to every diagnosis: a solid ink border reading "Final · LLM judge", or a dashed border reading "Preliminary · term-overlap estimate" (plus "judge pending" or "judge failed" when that applies). In tables it shows the word alone, with the method in the tooltip and screen-reader text.

### Motion (public pages)
One family of moves, all from the product's vocabulary, eased out (`cubic-bezier(0.16, 1, 0.3, 1)`), and every one settles to its finished state under reduced motion. The home page has three moments; everything else is quiet.
- **The case opens** (hero): the case file comes into focus from a soft blur, then the run assembles once, in about four seconds: the question types in, the answer prints, each stage is checked, a hand-drawn red ring closes around Grounding, the estimate is struck as the judge takes over, and the verdict lands, large. It's built for a three-second read: the retrieved chunks fold into one line that opens, and the verdict is above the fold at 1280×720. Replay restarts it. In the hero, red appears three times: the headline stroke, the ring (with its stage bar), and the verdict.
- **The red thread**: one 1.5px red line from under the case file, down the left gutter past a pin at each chapter about the run, to the recovery run's healthy attempt. It draws as the reader scrolls, with a small tip where it's being drawn. Desktop only; phones get small red pins instead.
- **The light table**: a pinned section where the run's five layers (question, context, answer, the judge's checks, verdict) lift apart in perspective, then each is pulled out of the stack in turn. The answer layer is red throughout. Clicking a layer lays it flat for reading (Esc returns). CSS 3D on real elements, no canvas. Phones and reduced motion get the five sheets as a grid.
- **The benchmark stream** (under the hero): the 117 labelled cases behind the accuracy figures, in three rows (term overlap, embeddings, the judge), each mark a stage sequence drawn as the dashboard draws one, a ring on every wrong diagnosis. The rows drift in alternating directions; the pointer slows them and names the case. Data from `docs/benchmarks`, nothing invented.
- **Between sections** (CSS scroll-driven, static where unsupported): headings, intro text and the main figures come into focus from a soft blur as they scroll in; the light table's room dims as you arrive and brightens as you leave; a stage's red bar draws across; the rule between numbered steps draws down; rows that are a sequence (issues, recovery attempts) arrive in order; side-by-side pairs (a figure and its code) meet from the left and the right.
- **Routes diagram** (Works with what you run): available routes carry a navy packet into TraceroAI and out to what it produces; planned routes are dashed and still.
- Smaller: the trace in section two folds from 18 lines to three as you scroll; the trace record behind the hero comes into focus under the cursor; headings wipe in; figures and numbers reveal once; the terminal types its commands once.
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

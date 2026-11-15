---
version: 1
slug: "traceroai-web-src-app-dashboard"
primary_target: "traceroai-web/src/app/dashboard"
related_targets: []
---

# Dashboard surface brief

Scope: the signed-in dashboard (`traceroai-web/src/app/dashboard`): overview, traces list, trace detail, eval runs, loading, error and empty states. Mode: Operate.

Audience and job: an AI engineer investigating a bad RAG answer, often from a trace id in their logs; long investigations, reading judge reasons and retrieved chunks. Wrong if it reads as a generic admin template, is playful, hides evidence, or is too dense to read. Light theme is pinned.

## Direction contract

THESIS: Every bad answer is an incident report: a sequence of stages (Retrieval, Grounding, Answer), the findings for each, and one probable cause. Refuses the category default of a grey metric-card grid with score percentages.

OWN-WORLD: White report stock for work areas on a pale docket blue-grey rail (#eef2f6); ink #14202e; institutional navy #1d3a5f for navigation selection, links and focus; red #b42318 reserved for the probable cause and nothing else; green passed, amber unclear. Public Sans for text, IBM Plex Mono for ids, sources and scores. Structure from 1px rules, square-ish 4px corners, no shadows or floating cards. Estimated verdicts are hatched, judged ones solid; an overruled estimate stays visible, struck through.

STORY: The engineer sees which stage broke and whether the judge or an estimate said so, reads the reason and the chunks that were (or were not) retrieved, then changes the pipeline.

FIRST VIEWPORT: Left docket rail (wordmark, project select, nav with counts, judge and queue status at the foot). On Traces: a quieted list column (filters, rows with a three-segment sequence and the diagnosis) beside the open trace: question as the title, meta line with copy id, "Probable cause" verdict with Final/Preliminary mark, the three-stage ruled sequence with the failing stage marked, then tabs (chunks, prompt, answer, evaluation, feedback, JSON). Signature move: the stage sequence with its probable-cause marker, repeated small in every list row.

FORM: Investigation Docket (accident investigation report), candidate 3 of 7 on the ordered list; seed:7106624d22d37b97.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

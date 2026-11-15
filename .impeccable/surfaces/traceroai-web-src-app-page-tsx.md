---
version: 1
slug: "traceroai-web-src-app-page-tsx"
primary_target: "traceroai-web/src/app/page.tsx"
related_targets: []
---

# Landing page surface brief

Scope: the public home page (`traceroai-web/src/app/page.tsx`). Mode: Persuade. World: the dashboard's Investigation Docket (DESIGN.md), light.

Audience and action: an AI engineer with their own RAG pipeline. They should come away believing TraceroAI tells them which stage failed and how sure it is, and act by installing the SDK or self-hosting. Proof: real dashboard screenshots from the example app, the published accuracy benchmark, the open source repo. No testimonials, logos or invented numbers.

## Direction contract

THESIS: The page is a short technical report on TraceroAI: an abstract, findings, method, measured accuracy and how to reproduce it, with a contents rail. Refuses the AI SaaS template of a centred gradient headline over a row of feature cards.

OWN-WORLD: The dashboard's report stock: white page, docket-rail tints, 1px rules, Public Sans headlines and IBM Plex Mono for code and ids, navy for actions, red only for a probable cause shown in a figure. Figures are real screenshots in ruled frames with numbered captions ("Figure 1."). Code blocks in dark ink are the one dark element.

STORY: A wrong RAG answer is a lookup, not a guess: TraceroAI names the stage that broke, says whether the judge or an estimate decided, can heal it, can prove a change helped, and runs on your own machine.

FIRST VIEWPORT: Top bar (wordmark, Docs, Architecture, Accuracy, GitHub, Open the dashboard). Left: sticky contents rail (Summary, What it finds, How it decides, Self-healing recovery, Experiments, Measured accuracy, Architecture, Run it yourself) that tracks the section in view. Centre: the title "Know which stage of your RAG pipeline failed.", a two-sentence abstract, `pip install traceroai` with copy, Quickstart and GitHub, a facts line (Apache-2.0, Docker Compose, judge accuracy 94 to 96% on 117 labelled traces). Right: Figure 1, the real trace verdict and stage findings with its recovery run.

FORM: The technical report, structure 6 of 7 on the ordered list; seed:5e179f6b33f762cb.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

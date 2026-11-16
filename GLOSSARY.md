# Glossary

The words TraceroAI uses in its code, interface and docs. Use these terms; the
"avoid" lists name the synonyms that cause confusion.

## Recording

**Trace**
One run of the user's pipeline or agent, recorded from input to output: the question,
what was retrieved or called, the answer, timings and cost. One trace answers one input.
_Avoid:_ request, log, event.

**Step** *(planned)*
One unit of work inside a trace: a model call, a retrieval, a tool call, or an agent turn.
Steps nest. In the interface and docs it is always "step".
_Avoid:_ node, event, action.

**Span** *(planned)*
The OpenTelemetry record of a step. Used only when talking about the data model or
OpenTelemetry ingest; everywhere else, say "step".

**Stage**
For RAG traces, one of the three parts a diagnosis can blame: retrieval, grounding, or
the answer. Stages predate steps; a RAG stage maps to one or more steps.

**Project** and **environment**
A project groups the traces of one application; the environment (dev, staging,
production) says where a trace came from. A project key can read and write only its
project.

## Judging

**Check**
One evaluation of one part of a trace, such as "is every claim supported by the
context". In code: an evaluator.
_Avoid:_ metric, eval (as a noun for a single check).

**Finding**
The result of one check: a label, an optional score, and a reason. A diagnosis is
derived from findings.

**Diagnosis**
The single conclusion for a trace: a label (for example "retrieval miss"), a reason, its
source, and the stage or step it blames. Every trace has exactly one.
_Avoid:_ score, grade, verdict (except in "judge verdict" below).

**Probable cause**
The stage or step a diagnosis blames, as the interface shows it. The only thing drawn in
red.

**Source** (of a diagnosis)
What decided it. An **estimate** comes from a cheap method (term overlap, or embedding
similarity); a **judge verdict** comes from the LLM judge. The interface says
"Preliminary" for an estimate and "Final" for a judge verdict.
_Avoid:_ confidence (we report the source, not a probability).

**Healthy**
A trace whose diagnosis is "healthy answer" or "correct refusal".

**Needs review**
The diagnosis when the checks disagree or can't decide. Not a failure, not a pass.

## Acting on failures

**Issue** *(planned)*
A group of failing traces that share a cause, identified by a **signature** (the
diagnosis label plus, for example, the document or tool involved). An issue is open,
resolved, or regressed.
_Avoid:_ cluster, incident.

**Recovery run**
The attempts the recovery agent made for one question. Each **attempt** is a trace; the
change made before an attempt is its **lever** (retrieve more, or a stricter prompt).

**Experiment**
A comparison of pipeline **variants** (for example top_k 3 versus 5) on a labelled set of
questions, each question a **case**.

**Dataset** *(planned)*
A saved set of cases, built from traces or issues, that experiments and the regression
gate run against.

**Field trial** *(planned)*
Using TraceroAI on a real open-source project to improve its results, and feeding what
breaks back into TraceroAI.

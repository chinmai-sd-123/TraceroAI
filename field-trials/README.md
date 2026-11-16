# Field trials

TraceroAI is tested on its own example app and a labelled set. Field trials put it in
front of real open-source projects it wasn't built around: instrument the project, use
TraceroAI's diagnoses to improve its answers, measure the result on questions held back
from tuning, and check the measurements by hand.

Each trial reports what it found, including where TraceroAI was wrong, and what that
changed in TraceroAI. Results that don't improve are reported too.

| Trial | Project | What it found |
|---|---|---|
| [1](01-librechat-rag-api/) | LibreChat's rag_api | A prompt that invites answers from memory; four places TraceroAI needed work, three fixed |

Rules each trial follows:

- Work happens in a local copy. Nothing is sent to the project's repository.
- A change is claimed only when it holds on held-back questions and a hand check of the
  grading agrees.
- Each trial caps its model spend (50 cents of generation) and reports what it used.

#!/usr/bin/env bash
# The trial's documents: 12 pages of FastAPI's tutorial (MIT licence), as of 2026-11-16.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p corpus
for page in first-steps path-params query-params body response-model handling-errors \
            background-tasks middleware cors bigger-applications dependencies/index security/first-steps; do
  curl -fsS "https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/tutorial/$page.md" \
    -o "corpus/$(echo "$page" | tr '/' '-').md"
done
echo "fetched $(ls corpus | wc -l) pages into corpus/"

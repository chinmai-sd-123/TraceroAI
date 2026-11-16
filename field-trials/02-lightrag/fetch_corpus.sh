#!/usr/bin/env bash
# The trial's documents: six pages of LightRAG's own documentation (MIT licence),
# from github.com/HKUDS/LightRAG at 9234426 (2026-11-16).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p corpus
for page in AsymmetricEmbedding ThirdPartyChunker ParserServiceDeployment OfflineDeployment \
            RoleSpecificLLMConfiguration MultiSiteDeployment; do
  curl -fsS "https://raw.githubusercontent.com/HKUDS/LightRAG/9234426/docs/$page.md" -o "corpus/$page.md"
done
echo "fetched $(ls corpus | wc -l) pages into corpus/"

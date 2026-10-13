#!/usr/bin/env bash
# Full-corpus extraction
set -euo pipefail
cd "$(dirname "$0")/.."

caffeinate -i -w $$ &
export PYTHONUNBUFFERED=1

# Two passes
for pass in 1 2; do
  uv run --env-file .env pg extract-set glm-high --workers 48 2>&1 | tee -a corpus_run.log
done

uv run pg build-edges glm-high
uv run pg resolve-names glm-high 2>&1 | tee -a corpus_run.log

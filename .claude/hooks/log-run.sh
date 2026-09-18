#!/usr/bin/env bash
# SessionEnd: append a one-line session record to runs/SESSIONS.md.
#
# Metadata and references only — never raw conversation content. The value is
# being able to answer "what did I actually try in March?" without re-reading
# transcripts.

set -euo pipefail
mkdir -p runs
stamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
runs=$(find runs -maxdepth 1 -type d -name '2*' 2>/dev/null | wc -l | tr -d ' ')
champ="none"
[ -f champion/champion.json ] && champ=$(python3 -c "import json;print(json.load(open('champion/champion.json'))['task'])" 2>/dev/null || echo "unreadable")

[ -f runs/SESSIONS.md ] || echo "# Session log

Append-only. Metadata only — no conversation content.
" > runs/SESSIONS.md

echo "- \`$stamp\` — runs on disk: $runs, champion: $champ" >> runs/SESSIONS.md
echo '{}'

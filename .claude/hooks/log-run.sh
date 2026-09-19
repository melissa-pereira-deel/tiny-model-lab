#!/usr/bin/env bash
# SessionEnd: append a one-line session record to runs/SESSIONS.md.
#
# Metadata and references only — never raw conversation content. The value is
# being able to answer "what did I actually try in March?" without re-reading
# transcripts.
#
# This used to append unconditionally and ignore stdin, which produced ten
# identical lines inside four seconds (#13) and left no way to find out why.
# Two changes came out of that:
#
#   1. It reads the payload. SessionEnd carries `session_id` and `reason`
#      (clear | resume | logout | prompt_input_exit | other). Naming the
#      session is what actually distinguishes entries — `runs` and `champion`
#      are near-constant early on, which is why the burst looked identical —
#      and recording `reason` means the next burst is diagnosable instead of
#      mysterious. #13 guessed subagents; the docs rule that out, since a
#      subagent finishing fires SubagentStop, not SessionEnd. The mechanism is
#      still unknown.
#
#   2. It skips a write that would say nothing new, comparing against the last
#      line with its timestamp stripped. The file stays append-only: nothing is
#      ever rewritten, a repeat is simply not written.
#
# Known limit: read-then-append is not atomic, so two fires in the same instant
# could both append. flock is not on macOS by default and a markdown ledger does
# not earn a lock file.
#
# Never fail. A logging hook that breaks a session is worse than no log, so
# every field degrades to a placeholder rather than erroring.

set -euo pipefail

root="${CLAUDE_PROJECT_DIR:-.}"
log="$root/runs/SESSIONS.md"

input=$(cat 2>/dev/null || echo "")

# python3 is not on PATH under Git Bash on Windows. Unlike the guard, this hook
# has nothing to protect, so a missing interpreter degrades to placeholders
# rather than refusing.
PY=$(command -v python3 || command -v python || echo "")

read -r session reason <<<"$(
  [ -n "$PY" ] && printf '%s' "$input" | "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
sid = str(d.get("session_id") or "unknown")[:8] or "unknown"
print(sid, str(d.get("reason") or "unknown"))
' 2>/dev/null || echo "unknown unknown"
)"

mkdir -p "$root/runs"
stamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Run directories are timestamped, so the newest sorts last. No mapfile and no
# negative array index: macOS ships bash 3.2 and this hook runs there first.
found=$(find "$root/runs" -maxdepth 1 -type d -name '2*' 2>/dev/null | sort || true)
runs=0
latest=""
if [ -n "$found" ]; then
  runs=$(printf '%s\n' "$found" | wc -l | tr -d ' ')
  latest=", latest $(basename "$(printf '%s\n' "$found" | tail -n 1)")"
fi

champ="none"
if [ -f "$root/champion/champion.json" ]; then
  champ="unreadable"
  [ -n "$PY" ] && champ=$(
    "$PY" -c "import json;print(json.load(open('$root/champion/champion.json'))['task'])" \
      2>/dev/null || echo "unreadable"
  )
fi

[ -f "$log" ] || printf '%s\n' "# Session log" "" \
  "Append-only, one line per session. Metadata only — no conversation content." "" > "$log"

body="session $session ($reason) — runs: $runs$latest, champion: $champ"

# Everything after the timestamp. If it matches the previous entry, this fire
# learned nothing and writing it would only make the ledger harder to read.
previous=$(tail -n 1 "$log" 2>/dev/null | sed -E 's/^- `[^`]*` — //')
if [ "$previous" != "$body" ]; then
  echo "- \`$stamp\` — $body" >> "$log"
fi

echo '{}'

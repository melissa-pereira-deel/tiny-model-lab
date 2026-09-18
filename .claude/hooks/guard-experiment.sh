#!/usr/bin/env bash
# PreToolUse guard: refuse to start training without a valid experiment file.
#
# This is a feedforward guide in Böckeler's sense — it steers before the agent
# acts. The point is not to catch a careless agent; it is to make "just try
# something quickly" cost an explicit, visible decision.

set -euo pipefail
input=$(cat)
command=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || echo "")

case "$command" in
  *train.py*|*"python -m harness.train"*)
    if ! ls experiments/*.yaml >/dev/null 2>&1; then
      cat <<'MSG'
{"decision":"block","reason":"No experiment file found in experiments/. Training without one is how runs become unaccountable. Run /scope first to produce an experiment.yaml with a named baseline and explicit budgets."}
MSG
      exit 0
    fi
    ;;
esac
echo '{}'

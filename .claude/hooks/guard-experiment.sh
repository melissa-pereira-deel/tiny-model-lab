#!/usr/bin/env bash
# PreToolUse guard: refuse to start training without a valid experiment file.
#
# This is a feedforward guide in Böckeler's sense — it steers before the agent
# acts. The point is not to catch a careless agent; it is to make "just try
# something quickly" cost an explicit, visible decision.
#
# On the patterns below: this repo has no harness/train.py and deliberately
# should not have one. The harness core stays dependency-light (torch is an
# optional extra), so the actual training script belongs to your experiment,
# not to the harness. The guard therefore matches where training really
# happens: a script with "train" in its name, and anything run out of
# experiments/, which is where /scope writes its contract.
#
# The patterns require an interpreter, not just a mention. Matching bare
# filenames looks safer but is not usable: it blocks `git commit` on a message
# that discusses train.py, and it blocks editing this file. A guard that fires
# on prose gets switched off, and a switched-off guard protects nothing.
#
# Known limit: this is a filename-level check, not a dataflow one. It cannot
# tell that experiments/a.yaml is the contract for experiments/b-train.py. It
# is a tripwire against forgetting the step, not a proof of correctness.

set -euo pipefail
input=$(cat)
command=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || echo "")

root="${CLAUDE_PROJECT_DIR:-.}"

# The repo's own worked example carries its experiment.yaml next to it, and is
# run by CI and by the README's one-second promise. Never block it.
case "$command" in
  *examples/01-hello-tiny/run.py*) echo '{}'; exit 0 ;;
esac

case "$command" in
  *python*train*.py*|*python*"harness.train"*|*python*experiments/*|\
  *"uv run"*train*.py*|*"poetry run"*train*.py*|./*train*.py*)
    if ! compgen -G "$root/experiments/*.yaml" >/dev/null 2>&1; then
      cat <<'MSG'
{"decision":"block","reason":"No experiment file found in experiments/. Training without one is how runs become unaccountable. Run /scope first to produce an experiment.yaml with a named baseline and explicit budgets."}
MSG
      exit 0
    fi
    ;;
esac
echo '{}'

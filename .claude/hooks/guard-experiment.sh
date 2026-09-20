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
#
# On spikes: a spike record is experiments/<slug>.spike.md, and the unlock
# below globs experiments/*.yaml, so a spike does not unlock training. That is
# the whole reason the record is Markdown — a spike is a measurement, not a
# contract, and a file that authorised a training run by existing would be a
# way around /scope rather than a step before it. The patterns here are
# unchanged; tests/test_guard_hook.py's spiked_project fixture is what holds
# the two apart, because nothing in this file mentions spikes at all.
#
# Spike *scripts* run free, which is deliberate: the point of a spike is to be
# cheap. Two consequences worth knowing. A spike script named *train*.py is
# still blocked, correctly — if your measurement trains something, it is an
# experiment. And the *python*experiments/* pattern below means a script run
# out of experiments/ is blocked whenever no contract exists, so spike code
# lives elsewhere (spikes/, tools/, anywhere) while the spike record lives
# here beside the contracts and the refusals.

set -euo pipefail
input=$(cat)

# python3 is not on PATH under Git Bash on Windows, and the old code piped to
# it with `|| echo ""` — so a missing interpreter produced an empty command,
# matched nothing, and the guard failed *open* without saying a word. A guard
# that silently stops guarding is worse than no guard, because you think you
# have one.
#
# The fallback is to match the raw payload instead of the parsed command.
# Cruder — it can fire on a command that merely mentions a training script —
# but the patterns below still need an interpreter and a path, so it is not
# indiscriminate, and it does not block every Bash call the way refusing
# outright would. Occasionally too loud beats quietly absent.
degraded=""
PY=$(command -v python3 || command -v python || true)
if [ -n "$PY" ]; then
  command=$(printf '%s' "$input" | "$PY" -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || echo "")
else
  command="$input"
  degraded=" (No Python interpreter on PATH, so the guard matched the raw hook payload rather than the parsed command. If that is a false positive, put python3 or python on PATH.)"
fi

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
      printf '{"decision":"block","reason":"%s%s"}\n' \
        "No experiment file found in experiments/. Training without one is how runs become unaccountable. Run /scope first to produce an experiment.yaml with a named baseline and explicit budgets." \
        "$degraded"
      exit 0
    fi
    ;;
esac
echo '{}'

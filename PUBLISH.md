# Publishing this repo

I couldn't push it myself — no GitHub credentials in my environment. Everything
below takes about a minute.

## Option A — GitHub CLI (fastest)

```bash
cd tiny-model-lab
gh auth status || gh auth login

gh repo create tiny-model-lab \
  --public \
  --source=. \
  --remote=origin \
  --description "A Claude Code harness for researching, training, and embedding tiny task-specific models" \
  --push
```

## Option B — web UI

1. Create an empty public repo named `tiny-model-lab` (no README, no .gitignore — this repo has both)
2. Then:

```bash
cd tiny-model-lab
git remote add origin git@github.com:YOUR-USERNAME/tiny-model-lab.git
git branch -M main
git push -u origin main
```

## Right after pushing

```bash
# Topics help people actually find it
gh repo edit --add-topic tiny-models,on-device-ai,edge-ai,claude-code,design-engineering,webgpu,machine-learning

# Two placeholders to replace with your username
grep -rn "YOUR-USERNAME" README.md pyproject.toml
```

Then check the Actions tab — CI runs the worked example and the 22 gate tests on
Python 3.10 and 3.12.

## Before you announce it

- [ ] Replace `YOUR-USERNAME` in `README.md` and `pyproject.toml`
- [ ] Confirm the copyright line in `LICENSE` is how you want to be credited
- [ ] Decide whether this lives standalone or as a sibling to `creative-technologist-agent` — the two share a philosophy (tiered risk, prototypes as output) and could cross-link
- [ ] Consider adding a second example that trains something real and exports to ONNX; the current example is deliberately dependency-free, which is honest but modest

## A note on the status section

The README says the subagents and skills "haven't been evaluated at scale."
Keep that until they have been. The fastest way to make this repo genuinely
useful — rather than merely well-argued — is to run three real tasks through it
and publish what broke.

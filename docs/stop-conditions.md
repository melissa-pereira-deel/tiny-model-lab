# Stop conditions

Define these before starting. Afterwards you'll be invested, and investment is
exactly what stop conditions exist to overrule.

## The five

| Gate | Fails when | Why it exists |
|---|---|---|
| **baseline** | Model doesn't *strictly* beat the named baseline | The single highest-value constraint here. Ties go to the baseline because it ships without weights. |
| **size** | Exported artifact exceeds the KB budget | Users download bytes, not parameters. |
| **latency** | p95 exceeds the latency band's ceiling | A model that misses its band changes what the interface must do. |
| **patience** | N consecutive evals with no strict improvement | Prevents the overnight loop that goes nowhere. |
| **wallclock** | Elapsed time exceeds the cap | Compute is finite; so is your week. |

## Kill criteria

Separate from gates, and written into `experiment.yaml` before training. Gates
stop a *run*. Kill criteria end a *project*. Examples:

- "Baseline still wins after two structural changes to the representation"
- "Cannot fit the size budget without dropping below baseline accuracy"
- "p95 stays above the band ceiling after quantization"

The harness refuses experiment files with an empty `kill_criteria` list. Naming
the conditions under which you'd walk away is uncomfortable in exactly the way
that makes it valuable.

## Rules for using them

**Never extend patience mid-run to rescue a plateau.** This is how a night
disappears. If the plateau is real, change something structural. A new seed is
not structural. A new learning rate is barely structural. A new input
representation is structural, and it's usually the thing that works.

**A failed baseline gate is not a signal to tune.** It's a signal to look at the
representation, then the labels, then the scoping. In that order. Hyperparameter
tuning is the most expensive possible way to discover that the task was
mis-scoped.

**Record the stop.** A run that stopped and said why is a result. The next person
— including you in three months — needs the reasoning more than the weights.

## The most common good outcome

The baseline wins and you ship the baseline.

This looks like failure and isn't. You spent a day learning something true about
the problem, and you have it written down. The alternative is shipping a model
that's worse than a regex while feeling good about its accuracy number, because
nobody measured the regex.

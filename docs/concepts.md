# Concepts, starting from analogies

No prior ML background assumed. Each section opens with an analogy, then builds
into the technical detail.

## What a "tiny model" is

**Analogy.** A spell-checker doesn't know what your sentence means. It does one
narrow thing extremely well, ships inside the app, and nobody calls it AI. It's
just infrastructure.

A tiny model is that, learned instead of hand-coded. Kilobytes to a few
megabytes, one narrow job, running on the user's machine. The reference example
is gpu-lexer: 27.5KB, syntax-highlights code in a browser, and infers the
language rather than being told. For comparison, a general-purpose language
model is measured in gigabytes and runs in a datacentre.

**Technically:** a small neural network, often under a million parameters,
trained for a single task with a closed output space, quantized to low
precision, and compiled into the application bundle.

## Why local matters (the four reasons)

**Analogy.** The difference between a colleague at the next desk and one you
have to email. Same knowledge, completely different interaction. You'll ask the
person next to you things you'd never bother emailing about.

That's latency changing what's worth asking. Concretely, local inference buys:

1. **Latency** — a network round-trip can't land under 100ms. Local can. Below 100ms an interaction feels like direct manipulation.
2. **Privacy** — data never leaves the device, which sometimes makes a feature legal to ship at all. Health, finance, journaling, unreleased work.
3. **Offline** — planes, subways, rural areas, construction sites.
4. **Cost at frequency** — near-zero marginal cost per inference means you can run it on every keystroke rather than rationing it behind a button.

If a feature doesn't win on at least one of these, use an API.

## Training, fine-tuning, distillation

**Analogy.** Training from scratch is teaching someone a job with no prior
experience. Fine-tuning is retraining an experienced hire for your specifics.
Distillation is having your best employee teach an apprentice — the apprentice
never reaches the expert's breadth, but for the one task they do all day, they
get close, and they're much cheaper to employ.

**Technically:** distillation trains a small student on the large teacher's full
probability distribution rather than just the correct answers. Those soft targets
carry more information — the teacher's uncertainty tells the student which
mistakes are reasonable. This is often called "dark knowledge".

## Quantization

**Analogy.** Deciding how many decimal places to keep. Storing π as 3.14159
instead of 3.14159265358979 saves space, and for most purposes changes nothing.
Round to 3 and your circles come out wrong.

**Technically:** weights are normally 32-bit floats. Quantizing to 8, 6, or 4
bits shrinks the model proportionally. Two approaches:

- **Post-training quantization** — compress an already-trained model. Cheap, immediate, usually fine at 8-bit.
- **Quantization-aware training** — simulate the rounding *during* training so the model learns weights that survive it. Needed below 8-bit. gpu-lexer ships int6 this way.

The trap: quantization failures are silent. The model still loads and produces
plausible output. Always compare against the full-precision version and report
the disagreement rate.

## Representation (the one that actually matters)

**Analogy.** A well-organised kitchen makes an average cook fast. A chaotic one
slows down an expert. The arrangement of the ingredients does more work than the
skill of the cook.

For tiny models, how you present the input matters more than the architecture.
gpu-lexer doesn't tokenise per language — a plain deterministic pass splits text
into word runs, whitespace, newlines, and symbols, recording language-neutral
features like length, edge characters, and neighbouring symbol pairs. The model
only has to learn the residual. That framing *is* the invention.

Practical consequence: when a tiny model plateaus, change the representation,
not the hyperparameters. The `01-hello-tiny` example demonstrates this — the toy
model sees only the first character, and 16× more data buys it 1.6 points before
it stops improving entirely.

## Inductive bias, and the "bitter lesson"

**Analogy.** Teaching someone to read music. You could let them figure out the
patterns from thousands of examples, or you could just tell them the staff has
five lines. Telling them saves enormous time. Telling them "always play Bach
slowly" also saves time and will eventually hold them back.

**Technically:** inductive bias is structure you build into the model rather than
making it learn. Convolutions assume nearby things are related; that's a bias,
and a good one for images and text.

Sutton's "bitter lesson" argues that general methods leveraging computation
eventually beat handcrafted structure. At tiny scale with little data, you're in
the opposite regime. The distinction worth holding (from Kyle Cranmer): bake in
biases grounded in the **mathematical structure of the data** — locality,
symmetry, order. Don't bake in **your heuristics about how the task should be
solved**. The first ages well; the second becomes your ceiling.

## Latency bands

**Analogy.** Conversation. Under a tenth of a second, a response feels
simultaneous. Around a second, it's a normal exchange. Ten seconds and you check
whether the call dropped.

**Technically** (Miller 1968, Nielsen 1993):

| Band | Ceiling | Design consequence |
|---|---|---|
| Instant | 100 ms | Feels like direct manipulation. No spinner needed. |
| Flow | 1 s | Thought unbroken, but the seam is felt. |
| Attention | 10 s | Needs visible progress or you lose them. |

These are facts about human perception, unchanged since 1968. They're the
clearest argument for on-device inference, and they're why the latency gate is
expressed in bands rather than raw milliseconds — the band tells you what the
*interface* has to do.

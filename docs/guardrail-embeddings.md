# How the safety check understands messages

The [safety net](guardrail.md) has to recognize risky messages ("how do I wire this to 230 volts?", "ignore your
rules") in any wording, in English or German, without slowing the chat down and without a second AI. This page
explains how it does that with **embeddings**, and how it was tuned.

**In short:** every message is turned into a point on a "meaning map". The map also holds about 170 hand-written
example sentences, grouped by category. A message is blocked only when it lands clearly close to the risky examples;
everything else goes to the agent.

---

## 1. Embeddings: a map of meaning

![A sentence becomes 768 numbers, which place it as a point on a meaning map among example sentences](images/guardrail-meaning-map.svg)

An **embedding** is a list of numbers (here 768) that Gemini computes for a sentence. The numbers capture what the
sentence *means*, not which words it uses. Two sentences with similar meaning get similar numbers, so they land close
together on the map, even when they share no words or are in different languages:

- "How do I connect the thermostat to the mains?" and "Wie schließe ich das Thermostat an 230 V an?" land next to
  each other.
- "Which thermostat works with Alexa?" lands far away from both.

The real map has 768 directions instead of 2, but the idea is the same: **closeness means similar meaning.**

## 2. Example sentences mark the areas

Instead of keyword lists or a trained model, each category is described by example sentences that someone wrote by
hand:

| Category | Examples | What happens |
|---|---|---|
| **Smart home** (including small talk and "answer in English please") | 104 | Always passes. |
| **Electrical work** (wiring, mains, installation steps) | 17 | Blocked: fixed reply recommending an electrician. |
| **Prompt tricks** (attempts to override the instructions) | 17 | Blocked: fixed reply. |
| **Off-topic** (recipes, weather, homework, ...) | 36 | Passes; the agent redirects, and the [answer check](guardrail.md#the-answer-check) catches off-topic replies. |

The examples are embedded once when the agent starts and kept in memory. Changing the behavior means editing
readable sentences, not retraining anything.

The smart home group deliberately includes sentences that *look* risky but are fine: "Does this thermostat need a
neutral wire?" is a product question, not a wiring instruction, and "forget what I said about my budget" is the
customer editing their own request, not a prompt trick.

## 3. Scoring a message and deciding

![Compare the message with all examples, score each category, then decide with three conditions](images/guardrail-scoring.svg)

1. **Compare.** The message is embedded once and compared with every example sentence. Closeness is a number from
   0 (unrelated) to 1 (same meaning).
2. **Score each category.** A category's score is the average of its **two** closest examples. Using two instead of
   one means a single lookalike sentence cannot decide alone.
3. **Decide.** The message is blocked only if all three conditions hold: the winning category is a blocking one, its
   score clears that category's bar, and it clearly leads the runner-up. Otherwise it goes to the agent unchanged.

The bars, as set today:

| Category | Bar | Why this value |
|---|---|---|
| Electrical work | 0.78 | Real wiring questions scored from about 0.80; harmless messages with electrical on top stayed below 0.72. |
| Prompt tricks | 0.70 | Real tricks scored 0.72 to 0.87; no harmless message ever had this category on top. |
| Off-topic | 0.66 | Used by the answer check. Messages under 3 words are never treated as off-topic. |

All values can be changed through `AGENT_GUARDRAIL_*` settings without touching the code.

## 4. How it was tuned

The setup was improved over five rounds, always with the same method:

- a **practice set** of example conversations (171 messages) to choose settings on, and
- a separate **test set** (68 messages) written *before* measuring and never used to choose anything, so the reported
  numbers show how the check handles messages it has never seen.

Two real conversations shaped the result, and both were fixed by adding the missing kind of harmless message to the
smart home examples:

- **"im diego"** (after "what's your name?") was answered with the off-topic reply. Short messages without content
  sat almost equally close to every category, so the choice was nearly a coin flip.
- **"Answer me in English please"** and **"forget what I said about the budget"** were treated as off-topic or as a
  prompt trick. Conversation control ("repeat that", "start over", "in German please") now has its own examples.

The biggest single improvement came from one embedding setting, the **task type**. Gemini can tune its numbers for
different jobs; switching from "similarity" to "classification" pulled small talk and off-topic questions apart:

![Before: small talk and off-topic overlap near zero. After: small talk is clearly on the pass side](images/guardrail-tuning.svg)

With the classification setting, every small talk and conversation-control message in both sets has "smart home" on
top. It is safe because of the ranking, not because of a threshold sitting exactly at the edge.

Finally, the product owner decided that off-topic messages should not be blocked at the door at all: a friendly
redirect by the agent is better than a canned refusal, and off-topic *answers* are still caught by the answer check.

### Where it stands

| | Practice set (171) | Test set (68) |
|---|---|---|
| Wiring questions blocked | 15 of 15 | 4 of 5 |
| Prompt tricks blocked | 16 of 16 | 9 of 9 |
| Harmless messages wrongly blocked | 0 of 114 | 0 of 42 |

The one missed wiring question was borderline ("can I connect the switch without the neutral, just the live and load
wire?"). If the agent tried to answer it with instructions, the answer check would still replace the reply.

## 5. Why not ask a second AI?

- **Speed and cost:** one embedding call plus about 170 quick comparisons takes milliseconds; a second AI would add a
  full answer's worth of time and cost to every message.
- **It cannot be talked into anything:** an AI judge can itself be tricked by a clever prompt. A distance on a map
  cannot.
- **Easy to adjust:** behavior changes by editing example sentences that anyone can read.

## 6. Limits

- It is a strong signal, not a guarantee. Unusual phrasings, long mixed messages or other languages may pass; the
  agent's own rules and the answer check are the next lines of defense.
- Each message is judged on its own, not the whole conversation.
- If the embedding service is unavailable, messages pass (the chat must never stop), and the agent's rules apply.
- The sets are small and hand-written. The next improvement is to learn from real messages the check was unsure
  about, not to lower the bars.

## Keeping it calibrated

After editing example sentences or evaluation cases, or changing the embedding model, re-measure and refresh the
recorded vectors that the tests use:

```bash
uv run python -m evals guardrail --sweep --record
```

The tests then run the real check offline on those recorded vectors; no test calls Gemini.

## For developers: where to look

| Topic | Code |
|---|---|
| Example sentences | `src/smart_home_agent/guardrail/input/prototypes.py` |
| Scoring and decision | `src/smart_home_agent/guardrail/input/` (`SemanticGuardrail`, `_decision_rule.py`, `thresholds.py`) |
| Embedding setting (task type) | `src/smart_home_agent/guardrail/input/embedding.py` |
| Practice and test messages | `evals/guardrail_cases.py` |
| Default bars | `src/smart_home_agent/config.py` (`guardrail_*`) |

---

[&larr; Safety net](guardrail.md) | [Overview](README.md)

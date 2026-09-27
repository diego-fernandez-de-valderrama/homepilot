# Known issues

Open problems that were found in testing and are not fixed yet. Each entry has the symptom, a reproduction, what is
known about the cause, and the proposed fix.

## 1. Reply language drifts to German after a language switch and a cart confirmation

**Status:** open, reproducible. **Area:** reply language (`session/language/`, `agent/prompts/instruction.py`),
cart confirmation (`agent/_turn_runner.py`, `agent/_confirmation_ledger.py`).

### Symptom

The customer writes in German, then switches to English and asks to add a product to the cart. After they confirm
the card, the reply is written in **German**. The next English message can stay German too (seen once in two runs).
Conversations that stay in one language are not affected.

### Reproduction

Terminal chat against a catalog that contains the Ledvance thermostat (`32332362`) and a Homematic IP thermostat:

```text
Ich suche ein Heizkörperthermostat für Homematic IP
Please add the Ledvance thermostat to my cart
y                                            <- confirms the cart card
```

```bash
uv run python -m smart_home_agent chat --user lang-test < script.txt
```

| Scenario | Runs | Reply after confirmation |
|---|---|---|
| German turn, then English add + confirm | 3 | German in 3 of 3 |
| English only, add + confirm | 2 | English in 2 of 2 |
| Next English message after the German confirmation reply | 2 | German in 1 of 2 |

Example of a wrong reply: "Ich habe das Ledvance Smart+ WiFi Heizkörper-Thermostat 1 Stück für 54,95 € in Ihren
Warenkorb gelegt." (the request was "Please add the Ledvance thermostat to my cart").

### What is known about the cause

- **Detection is correct.** `TurnLanguageDetector.detect("Please add the Ledvance thermostat to my cart")` returns
  `en` (the capitalized product name is dropped first), and `chat` stores it as `StateKey.TURN_LANGUAGE`.
- **The confirmation turn keeps that language.** `TurnRunner.confirm` passes no `TURN_LANGUAGE` in its
  `state_delta`, so the value from the English message stays, and `build_instruction` still adds "The customer's
  latest message is in English. Write your whole reply in English".
- **The model does not follow it on this turn.** The confirmation is sent as a `user` content that holds only a
  `function_response` (`ConfirmationLedger.answer`), so there is no customer text in the latest message. The model
  then follows the recent history, which is German (the previous answer plus the German catalog titles and cart
  lines in the tool result), and not the instruction. Wording that points at "the latest message" is weakest here,
  since that message has no words.
- **Nothing downstream catches it.** The output check (`guardrail/output/`) has no language check, and
  `ResilientGemini` only retries empty or stalled answers.
- A German reply to the confirmation also becomes part of the history, which explains the occasional German answer
  on the following English turn.

### Proposed fix

1. **Deterministic check with one retry (preferred).** After the model answers with text, detect the language of
   the reply with `TurnLanguageDetector` and compare it with `TURN_LANGUAGE`. On a confident mismatch, retry once
   with a one-line note ("Write the whole reply in English"), the same way `retrying.py` handles a stalled answer
   (`response_checks.py` + `retry_notes.py`). This does not depend on prompt wording, covers every turn type and
   keeps the note out of the session. Skip the check when either language is `None` (short or unclear text).
2. **Clearer instruction on confirmation turns (small, optional).** Mark the confirmation turn in the state (for
   example a flag set in `TurnRunner.confirm`) and let `_reply_language` say "The customer's last written message
   was in English; this turn only answers a cart confirmation". The project notes warn that small prompt changes
   have caused empty answers, so this must be measured live before it is kept.

### How to verify a fix

- Add a regression conversation to `evals/conversation.py` with the reproduction above and a language check on
  every turn (mark it `known_issue` until the fix lands, instead of weakening the check).
- Run `uv run python -m evals conversation --case <name> --repeat 5` before and after, and the full
  `uv run python -m evals conversation` to confirm nothing else regressed.
- Unit test the new check with a German reply to an `en` turn (retried) and an English reply (accepted).

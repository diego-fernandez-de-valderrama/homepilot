"""electrical: practical wiring / mains installation steps (EN/DE patterns, refusals excluded)."""

import re
from collections.abc import Sequence

from smart_home_agent.guardrail.output.violation import Violation

# Electrical: an instruction verb together with an electrical conductor/terminal term in one sentence.
_WIRE_TERMS = re.compile(
    r"\b(live|neutral|earth|ground|phase)\s+(wire|conductor|cable|lead|terminal)s?\b"
    r"|\b(brown|blue|black|grey|gray|green[- /]yellow|red)\s+(wire|cable|conductor|core)s?\b"
    r"|\bterminals?\s+(L|N|PE|L1|COM|NO)\b|\b(L|N|PE)\s+terminal\b|\bjunction box\b|\bmains\s+(cable|wire|supply)\b"
    # "Phase" alone is also the pairing phase, "Klemme" also a clip: only conductor and terminal forms count.
    r"|\bneutralleiter|\baußenleiter|\bschutzleiter|\bnullleiter|\bphasen?leiter|\badern?\b"
    r"|\b(anschluss|lüster|wago|reihen)klemmen?\b|\bklemmen?\s+(L|N|PE|L1)\b"
    r"|\b(braune|blaue|schwarze|graue|grün-gelbe)[nsr]?\s+(ader|kabel|leiter|draht)\b|\bunterputzdose\b|\babzweigdose\b",
    re.IGNORECASE,
)
_INSTRUCTION = re.compile(
    r"(^|[\s(\d.\-*•])(connect|attach|screw|insert|strip|twist|clamp|wire|hook up|join|disconnect)"
    r"\s+(the|it|both|each|your)\b"
    r"|\b(schließen|klemmen|verbinden|verdrahten|isolieren|stecken|schrauben|drehen)\s+sie\b"
    r"|\b(schließe|verbinde|verdrahte|isoliere)\b|\bklemme\s+(die|den|das)\b"
    r"|\b(anschließen|anklemmen|abisolieren|verdrahten)\s*[.:,]"
    r"|\b(switch|turn)\s+off\s+the\s+(circuit\s+)?(breaker|fuse)\b|\bsicherung\s+(aus|raus|herausdrehen|abschalten)",
    re.IGNORECASE,
)
# A sentence that refuses or hands the work to a professional. Incidental negations ("... and do not touch the blue
# wire") or a trailing "ask an electrician" inside an actual instruction do not make it a refusal.
_REFUSAL = re.compile(
    r"\b(i|we)\s+(can't|cannot|can not|won't|am not able to|'m not able to|am unable to|'m unable to)\b"
    r"|\b(can't|cannot|won't) (help|give|provide|explain|describe|walk you)\b"
    r"|\bnot (able|allowed) to (help|give|provide|explain|describe)\b"
    r"|\b(must|should|needs? to|has to) be (done|installed|carried out|connected|wired|fitted) by\b"
    r"|\bkann ich (leider )?nicht\b|\bkeine anleitung\b|\bnicht selbst\b"
    r"|\b(muss|müssen|sollte|sollten|darf|dürfen)\b.{0,40}\b(elektrofachkraft|elektriker)"
    r"|\b(durch|von) (eine|einen|einer|einem) (elektrofachkraft|elektriker)",
    re.IGNORECASE,
)


class ElectricalCheck:
    """A sentence with an instruction verb and a conductor/terminal term that is not a refusal."""

    def check(self, sentences: Sequence[str]) -> list[Violation]:
        return [
            Violation(kind="electrical", detail=sentence[:160])
            for sentence in sentences
            if _INSTRUCTION.search(sentence) and _WIRE_TERMS.search(sentence) and not _REFUSAL.search(sentence)
        ]

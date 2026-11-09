"""Whether a clause of the customer's message is about someone else (friend, family, gift, "sie hat ...")."""

import re

# Words that show a clause is about someone else (EN/DE), matched as whole words on the casefolded clause of the
# customer's message that contains the quote ("ß" is then "ss"). So "I'm buying it for my friend, I use Alexa
# myself" can still be stored with the quote "I use Alexa myself", while "My sister uses Alexa" cannot be stored
# as "uses Alexa".
# Plain plural pronouns are not listed ("I have Hue lights, they work great" is the customer's own fact).
_THIRD_PARTY = re.compile(
    r"\b("
    r"friends?|girlfriend|boyfriend|gifts?|mum|mom|mother|dad|father|parents?|brother|sister|wife|husband|"
    r"partner|son|daughter|kids?|children|grand\w*|uncle|aunt|cousin|nephew|niece|fianc\w*|in-laws?|"
    r"neighbou?rs?|colleagues?|boss|roommate|flatmate|relatives?|for (him|her|them)|"
    r"freund\w*|geschenk\w*|mama|papa|eltern|kind(er)?|enkel\w*|oma|opa|onkel|tante|nichte|neffe|"
    r"schwieger\w*|gro(ß|ss)(eltern|mutter|vater)|ehe(mann|frau|partner\w*)|verwandte[nr]?|bekannte[nr]?|nachbar\w*|"
    r"kolleg\w*|chef\w*|mitbewohner\w*|für (ihn|sie|ihre?n?)|"
    r"\w*(mutter|vater|bruder|schwester|sohn|tochter|eltern)|"
    r"(mein|meine|meinem|meinen|meiner|sein|seine|ihr|ihre|unser|unsere)\s+(frau|mann)"
    r")\b",
    re.IGNORECASE,
)
# A clause whose subject is another person ("Für meine Mutter: sie hat Alexa", "Er nutzt HomeKit").
_THIRD_PERSON_SUBJECT = re.compile(
    r"^(he|she|er|sie)\s+(has|uses|owns|likes|wants|prefers|hat|nutzt|benutzt|verwendet|besitzt|mag|will|möchte)\b",
    re.IGNORECASE,
)
_CLAUSE_BOUNDARY = re.compile(r"[.!?;:\n]+|,\s")


def about_someone_else(clause: str) -> bool:
    return bool(_THIRD_PARTY.search(clause) or _THIRD_PERSON_SUBJECT.match(clause))


def clauses(message: str, start: int, end: int) -> list[str]:
    """The clauses of the (normalized) message that overlap the quote at [start, end)."""
    found: list[str] = []
    position = 0
    for boundary in [*_CLAUSE_BOUNDARY.finditer(message), None]:
        clause_end = boundary.start() if boundary else len(message)
        if position < end and clause_end > start:
            found.append(message[position:clause_end].strip())
        position = boundary.end() if boundary else len(message)
    return [clause for clause in found if clause]


def own_clauses(message: str) -> list[str]:
    """The clauses of the (normalized) message that are not about someone else."""
    return [clause for clause in clauses(message, 0, len(message)) if not about_someone_else(clause)]

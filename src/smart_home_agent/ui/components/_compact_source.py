import re

from jinja2.ext import Extension


class CompactSource(Extension):
    """Removes every line break and the indentation after it from the template source (never from the values),
    so templates can be laid out on several lines while the HTML stays on one line: markdown would read an
    indented line as a code block, and whitespace between inline elements would show as a gap. A space that
    belongs to the output is written on the same line."""

    _BREAK = re.compile(r"\n\s*")

    def preprocess(self, source: str, name: str | None, filename: str | None = None) -> str:
        return self._BREAK.sub("", source)

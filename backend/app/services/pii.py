"""Mask personally identifiable information before text reaches an LLM (ADR-0003)."""

import re
from dataclasses import dataclass, field

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("SSN", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?!\d)")),
]


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


@dataclass
class MaskedText:
    text: str
    token_map: dict[str, str] = field(default_factory=dict)


class PiiMasker:
    """Replaces PII with stable tokens such as [SSN_1]; the same value always gets the same token."""

    def mask(self, text: str) -> MaskedText:
        token_map: dict[str, str] = {}
        by_value: dict[str, str] = {}
        counters: dict[str, int] = {}

        for kind, pattern in _PATTERNS:

            def replace(match: re.Match[str], kind: str = kind) -> str:
                value = match.group(0)
                if kind == "CARD":
                    digits = re.sub(r"\D", "", value)
                    if not 13 <= len(digits) <= 19 or not _luhn_valid(digits):
                        return value
                if value not in by_value:
                    counters[kind] = counters.get(kind, 0) + 1
                    token = f"[{kind}_{counters[kind]}]"
                    by_value[value] = token
                    token_map[token] = value
                return by_value[value]

            text = pattern.sub(replace, text)

        return MaskedText(text=text, token_map=token_map)

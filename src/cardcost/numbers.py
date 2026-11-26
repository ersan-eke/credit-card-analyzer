import re
from decimal import ROUND_HALF_UP, Decimal

_GERMAN = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
# Answer text may mix German (1.234,56) and English (1234.56 / 2.5) formats.
_ANY = re.compile(r"\d{1,3}(?:\.\d{3})+,\d+|\d+,\d+|\d+\.\d{1,2}(?!\d)|\d{1,3}(?:\.\d{3})+|\d+")


def parse_german_decimal(text: str) -> Decimal:
    """Parse the first German-formatted number in text: '1.234,56 EUR' -> Decimal('1234.56')."""
    m = _GERMAN.search(text)
    if not m or not _clean(text, m):
        raise ValueError(f"no German number in {text!r}")
    return Decimal(m.group().replace(".", "").replace(",", "."))


def _clean(text: str, m: re.Match[str]) -> bool:
    # reject '1,2,3' or '1.23.4': the match must not be glued to more digits/separators
    after = text[m.end() : m.end() + 2]
    return not re.match(r"[.,]\d", after)


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def number_spans(text: str) -> list[tuple[int, int, Decimal]]:
    out = []
    for m in _ANY.finditer(text):
        raw = m.group()
        if "," in raw:
            value = Decimal(raw.replace(".", "").replace(",", "."))
        elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
            value = Decimal(raw.replace(".", ""))
        else:
            value = Decimal(raw)
        out.append((m.start(), m.end(), value))
    return out


def find_numbers(text: str) -> list[Decimal]:
    return [v for _, _, v in number_spans(text)]

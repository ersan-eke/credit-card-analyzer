"""Score extracted rules against expected rules: recall and precision.

A rule is split per event and matches an expected one when price, allowance and stacking are equal as numbers and
`when` selects the same cases. Cases are a fixed grid of countries, ATM networks, merchants, weekend, amount
boundaries and fact values, plus the golden scenarios' countries, so two wordings of one condition count as equal.
"""

import functools
import itertools
from collections.abc import Callable
from decimal import Decimal
from typing import NamedTuple

from cardcost.models import Scenario

EVENTS = ("payment", "atm", "counter_cash", "holding", "credit")
GRID_COUNTRIES = ("DE", "FR", "AT", "PL", "US")  # home, eurozone, eurozone, EEA with own currency, outside the EEA
PRICE = ("percent", "flat_eur", "min_eur", "max_eur")
OTHER = "<other>"


class Hit(NamedTuple):
    label: str
    rule_id: str | None  # the expected rule's id (for an extracted rule: the one it matched, None if unmatched)
    hit: bool


class Score(NamedTuple):
    recall: float
    precision: float
    found: dict  # expected rule id -> the extracted rule its first event matched, or None
    missing: list  # (label, event, expected rule) with no match
    extra: list  # (label, event, extracted rule) matching nothing
    want: list  # one Hit per expected event
    got: list  # one Hit per extracted event of a scored label


def _dec(v) -> Decimal | None:
    return None if v is None else Decimal(str(v))


def _price(p) -> tuple | None:
    if p is None:
        return None
    percent, flat, low, high = (_dec(p.get(k)) for k in PRICE)
    if percent == 0 and not low:  # a zero price is the same in either unit; every other price stays strict
        percent, flat = None, flat if flat is not None else Decimal(0)
    return percent, flat, low, high


def _allowance(a) -> tuple | None:
    return None if a is None else (a.get("count"), _dec(a.get("amount_eur")), a.get("period"))


def _facts(w) -> dict:
    return w.get("facts") or {}


def _grid(whens: list[dict], countries) -> list[dict]:
    named = lambda key: {v for w in whens for v in (w.get(key) or [])}  # noqa: E731
    amounts = {Decimal(1), Decimal(100000)}
    for w in whens:
        for b in (w.get("amount") or {}).values():
            amounts |= {Decimal(b) + d for d in (Decimal("-0.01"), 0, Decimal("0.01"))}
    fact_names = sorted({n for w in whens for n in _facts(w)})
    fact_values = [[*sorted({v for w in whens for v in _facts(w).get(n, [])}), OTHER] for n in fact_names]
    return [
        {
            "country": c,
            "network": n,
            "merchant": m,
            "weekend": wk,
            "amount": a,
            "facts": dict(zip(fact_names, f, strict=True)),
        }
        for c, n, m, wk, a, f in itertools.product(
            sorted({*GRID_COUNTRIES, *countries, *named("country")}),
            sorted({"own", "other", *named("network")}),
            [None, *sorted(named("merchant"))],
            (False, True),
            sorted(amounts),
            itertools.product(*fact_values),
        )
    ]


@functools.cache
def _scenario(country: str) -> Scenario:
    return Scenario(kind="cash", amount_eur=1, country=country)


def _selects(w: dict, case: dict) -> bool:
    s = _scenario(case["country"])
    amount = w.get("amount") or {}
    return (
        all(w.get(k) is None or v in w[k] for k, v in (("currency", s.currency), ("region", s.region)))
        and (w.get("country") is None or case["country"] in w["country"])
        and (w.get("network") is None or case["network"] in w["network"])
        and (w.get("merchant") is None or case["merchant"] in w["merchant"])
        and (w.get("weekend") is None or w["weekend"] == case["weekend"])
        and ("min" not in amount or case["amount"] >= Decimal(amount["min"]))
        and ("max" not in amount or case["amount"] < Decimal(amount["max"]))
        and all(case["facts"].get(n) in vs for n, vs in _facts(w).items())
    )


def same_cases(a: dict, b: dict, countries=()) -> bool:
    return all(_selects(a, c) == _selects(b, c) for c in _grid([a, b], countries))


def matches(want: dict, got: dict, countries=()) -> bool:
    return (
        _price(want["price"]) == _price(got["price"])
        and _allowance(want.get("allowance")) == _allowance(got.get("allowance"))
        and bool(want.get("stacks")) == bool(got.get("stacks"))
        and same_cases(want.get("when") or {}, got.get("when") or {}, countries)
    )


def _atoms(rules: list[dict]) -> list[tuple[str, dict]]:
    return [(e, r) for r in rules for e in r["event"] if e in EVENTS]


def score(expected: dict[str, list[dict]], extracted: dict[str, list[dict]], countries=(), scored=None) -> Score:
    """Both: product label -> rules. Greedy one-to-one matching per label and event. Extracted rules of a label
    outside `scored` (None: all) count neither for nor against precision."""
    found, missing, extra, want_hits, got_hits = {}, [], [], [], []
    for label in sorted({*expected, *extracted}):
        want = _atoms(expected.get(label, []))
        got = _atoms(extracted.get(label, [])) if scored is None or label in scored else []
        taken: dict[int, str | None] = {}
        for event, w in want:
            i = next(
                (i for i, (e, g) in enumerate(got) if i not in taken and e == event and matches(w, g, countries)), None
            )
            want_hits.append(Hit(label, w.get("id"), i is not None))
            if i is None:
                missing.append((label, event, w))
                found.setdefault(w.get("id"), None)
                continue
            taken[i] = w.get("id")
            found.setdefault(w.get("id"), got[i][1])
        got_hits += [Hit(label, taken.get(i), i in taken) for i in range(len(got))]
        extra += [(label, e, g) for i, (e, g) in enumerate(got) if i not in taken]
    return Score(*tally_all(want_hits, got_hits), found, missing, extra, want_hits, got_hits)


def _ratio(hits: list[Hit]) -> float:
    return sum(h.hit for h in hits) / len(hits) if hits else 1.0


def tally_all(want: list[Hit], got: list[Hit]) -> tuple[float, float]:
    return _ratio(want), _ratio(got)


def tally(s: Score, keep: Callable[[str, str | None], bool]) -> tuple[float, float]:
    """Recall and precision over the events `keep(label, expected rule id)` selects; an extracted rule that matched
    nothing has id None, so it stays in every view of its label."""
    return tally_all([h for h in s.want if keep(h.label, h.rule_id)], [h for h in s.got if keep(h.label, h.rule_id)])

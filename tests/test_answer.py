from decimal import Decimal as D

from cardcost.answer import allowed_numbers, answer, bad_numbers
from cardcost.calc import rank
from cardcost.models import FeeSchedule, Scenario

ALPHA = FeeSchedule(
    card="alpha_card",
    percent=D("2.0"),
    min_eur=D("5.00"),
    source_file="a.pdf",
    source_page=2,
    confidence=1,
    quote="2,0 % ... mindestens 5,00 EUR",
)
GOLD = FeeSchedule(
    card="beta_card",
    product="Beta Gold",
    percent=D("1.0"),
    min_eur=D("7.50"),
    source_file="b.pdf",
    source_page=1,
    confidence=1,
    quote="1,0 % mind. 7,50 EUR",
)
FEES = {"alpha_card": ALPHA, "beta_card:Gold": GOLD}
S = Scenario(kind="cash", amount_eur=D("300"), country="DE")
TABLE = rank(FEES, S)


def _text(t: str) -> dict:
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": t}]}


class FakeLLM:
    def __init__(self, *texts):
        self.texts, self.requests = list(texts), []

    def create(self, purpose, prompt_version, **kw):
        self.requests.append(kw)
        return _text(self.texts.pop(0))


def test_german_formatted_table_numbers_pass():
    allowed = allowed_numbers(TABLE, FEES, S)
    assert bad_numbers("Die Alpha Card kostet 6,00 EUR für 300 EUR (2,0 %, mind. 5,00 EUR).", allowed) == []
    assert bad_numbers("Beta Gold kostet 7.50 EUR.", allowed) == []


def test_invented_number_triggers_regenerate_then_ok():
    llm = FakeLLM("Die Alpha Card kostet 5,99 EUR.", "Die Alpha Card kostet 6,00 EUR.")
    text, source = answer("Was kostet 300 EUR?", S, TABLE, FEES, llm)
    assert (text, source) == ("Die Alpha Card kostet 6,00 EUR.", "llm-retry")
    assert "5,99" in llm.requests[1]["messages"][0]["content"] or "5.99" in llm.requests[1]["messages"][0]["content"]


def test_two_bad_answers_fall_back_to_template():
    llm = FakeLLM("Kostet 1,23 EUR.", "Kostet 4,56 EUR.")
    text, source = answer("Was kostet 300 EUR?", S, TABLE, FEES, llm)
    assert source == "template"
    assert text.startswith("Am günstigsten für 300,00 EUR Bargeld (DE): alpha_card mit 6,00 EUR.")
    assert bad_numbers(text, allowed_numbers(TABLE, FEES, S)) == []

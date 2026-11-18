import re
from datetime import datetime, time
from decimal import Decimal
from typing import Literal, NamedTuple
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

from cardcost.numbers import find_numbers

EUROZONE = {
    "AT",
    "BE",
    "BG",
    "CY",
    "DE",
    "EE",
    "ES",
    "FI",
    "FR",
    "GR",
    "HR",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "MT",
    "NL",
    "PT",
    "SI",
    "SK",
}
EEA = EUROZONE | {"CZ", "DK", "HU", "IS", "LI", "NO", "PL", "RO", "SE"}
HOME = "DE"
NUMERIC_FIELDS = (
    "percent",
    "min_eur",
    "fx_percent",
    "atm_operator_fee_eur",
    "cash_interest_pa",
    "free_count",
    "free_amount_eur",
    "free_from_eur",
    "fx_free_eur",
)
# a fee of 0 is often written as a word, not "0,00"
FREE_WORDS = re.compile(r"kostenlos|kostenfrei|gebührenfrei|entgeltfrei|\bfree\b", re.IGNORECASE)


Currency = Literal["EUR", "EEA_non_EUR", "other"]
Region = Literal["home", "EEA", "outside_EEA"]  # EEA = the EEA outside the home country
Event = Literal["payment", "atm", "counter_cash", "credit"]
Period = Literal["calendar_month", "rolling_month", "year"]


class Window(BaseModel):
    """A weekly window as the bank states it. Days: Monday = 0. The default is Revolut's (Fri 17:00 - Sun 18:00 New
    York), the only one in the catalog: `weekend: true` in a rule means it."""

    # shortcut: one default window; upgrade to a window the extractor reads from the quote when a second bank has one
    start_day: int = Field(4, ge=0, le=6)
    start_time: time = time(17)
    end_day: int = Field(6, ge=0, le=6)
    end_time: time = time(18)
    tz: str = "America/New_York"

    def contains(self, at: datetime) -> bool:
        local = at.astimezone(ZoneInfo(self.tz))
        week = lambda d, t: (d * 24 + t.hour) * 60 + t.minute  # noqa: E731
        now, start, end = (
            week(local.weekday(), local.time()),
            week(self.start_day, self.start_time),
            week(self.end_day, self.end_time),
        )
        return start <= now < end if start < end else now >= start or now < end


class Amount(BaseModel):
    """The transaction amount in EUR: at least min ("ab 50 EUR"), below max ("unter 50 EUR")."""

    min: Decimal | None = Field(None, ge=0)
    max: Decimal | None = Field(None, ge=0)


class When(BaseModel):
    """Conditions a rule needs; each is a list of accepted values, and a rule with more conditions is more specific.
    Unset = any."""

    currency: list[Currency] | None = Field(None, min_length=1)
    region: list[Region] | None = Field(None, min_length=1)
    country: list[str] | None = Field(None, min_length=1)  # ISO codes, where the bank words it by country
    amount: Amount | None = None
    network: list[str] | None = Field(None, min_length=1)  # who owns the ATM: "own", a named group, or "other"
    merchant: list[str] | None = Field(None, min_length=1)
    weekend: Window | None = None

    @field_validator("weekend", mode="before")
    @classmethod
    def _weekend_flag(cls, v):
        return Window() if v is True else v

    @property
    def specificity(self) -> int:
        conditions = (self.currency, self.region, self.country, self.amount, self.network, self.merchant, self.weekend)
        return sum(v is not None for v in conditions)


class Price(BaseModel):
    """fee = amount x percent / 100 + flat_eur, then raised to min_eur and capped at max_eur."""

    percent: Decimal | None = Field(None, ge=0, le=100)  # event credit: the rate per year
    flat_eur: Decimal | None = Field(None, ge=0)
    min_eur: Decimal | None = Field(None, ge=0)
    max_eur: Decimal | None = Field(None, ge=0)

    @model_validator(mode="after")
    def stated(self) -> "Price":
        if all(v is None for v in self.model_dump().values()):
            raise ValueError("a price states at least one number; an unstated price is price=null")
        return self


class Allowance(BaseModel):
    """Free uses per period; both limits given = whichever is reached first. The price applies beyond it."""

    count: int | None = Field(None, ge=0)
    amount_eur: Decimal | None = Field(None, ge=0)
    period: Period

    @model_validator(mode="after")
    def limited(self) -> "Allowance":
        if self.count is None and self.amount_eur is None:
            raise ValueError("an allowance has a count or an amount")
        return self


class Rule(BaseModel):
    """One priced event under conditions. price=None: the document does not state it, so the cost is unknown."""

    name: str = Field(min_length=1)  # what the fee is called; names its part of the cost
    event: list[Event] = Field(min_length=1)
    when: When = When()
    price: Price | None
    allowance: Allowance | None = None
    stacks: bool = False  # adds to the matching base rule ("zzgl."); otherwise the most specific rule replaces
    quote: str = Field(min_length=1)
    page: int

    @property
    def is_fx(self) -> bool:
        return bool(self.when.currency) and "EUR" not in self.when.currency

    @property
    def numbers(self) -> list[Decimal]:
        stated = [
            *(self.price.model_dump().values() if self.price else []),
            *([self.allowance.count, self.allowance.amount_eur] if self.allowance else []),
        ]
        return [Decimal(v) for v in stated if v is not None]

    @model_validator(mode="after")
    def numbers_come_from_quote(self) -> "Rule":
        in_quote = set(find_numbers(self.quote))
        for value in self.numbers:
            if value not in in_quote and not (value == 0 and FREE_WORDS.search(self.quote)):
                raise ValueError(f"{self.name}: {value} does not appear in quote")
        return self


def _first(allowances: list["Allowance"], field: str):
    return next((v for a in allowances if (v := getattr(a, field)) is not None), None)


class Limits(NamedTuple):
    """The allowances a product has, to ask the user about: free withdrawals, free EUR, free EUR exchanged."""

    count: Decimal | int | None
    amount_eur: Decimal | None
    fx_eur: Decimal | None
    period: str | None


class FeeSchedule(BaseModel):
    """One product's fees as stated in the document. None = not stated; never guessed."""

    card: str
    product: str | None = None
    percent: Decimal | None = Field(None, ge=0, le=100)
    min_eur: Decimal | None = Field(None, ge=0)
    currency: str = "EUR"
    conditions: str | None = None
    fx_percent: Decimal | None = Field(None, ge=0, le=100)
    atm_operator_fee_eur: Decimal | None = Field(None, ge=0)
    cash_interest_pa: Decimal | None = Field(None, ge=0, le=100)
    free_count: Decimal | None = Field(None, ge=0)  # free withdrawals per period (see conditions)
    free_amount_eur: Decimal | None = Field(None, ge=0)  # free amount per period; whichever limit ends first
    free_from_eur: Decimal | None = Field(None, ge=0)  # withdrawals of at least this amount are free
    fx_free_eur: Decimal | None = Field(None, ge=0)  # exchange amount per period without FX fee; fx_percent beyond
    network: str | None = None  # card network (Mastercard, Visa): picks the ATM operator fee the user gave for it
    source_file: str
    source_page: int
    confidence: float = Field(ge=0, le=1)
    quote: str | None = None
    not_stated: list[str] = []
    rules: list[Rule] = []  # the rule format; when present the calculator prices from it, not from the fields above

    @property
    def limits(self) -> Limits:
        if not self.rules:
            return Limits(self.free_count, self.free_amount_eur, self.fx_free_eur, self.conditions)
        cash = [r.allowance for r in self.rules if r.allowance and not r.is_fx and "atm" in r.event]
        fx = [r.allowance for r in self.rules if r.allowance and r.is_fx]
        return Limits(
            _first(cash, "count"), _first(cash, "amount_eur"), _first(fx, "amount_eur"), _first(cash or fx, "period")
        )

    @model_validator(mode="after")
    def numbers_come_from_quote(self) -> "FeeSchedule":
        stated = {f: getattr(self, f) for f in NUMERIC_FIELDS if getattr(self, f) is not None}
        if stated and not self.quote:
            raise ValueError("quote is required when any fee is stated")
        in_quote = set(find_numbers(self.quote or ""))
        for name, value in stated.items():
            if value not in in_quote and not (value == 0 and FREE_WORDS.search(self.quote)):
                raise ValueError(f"{name}={value} does not appear in quote")
        return self


class Usage(BaseModel):
    """Withdrawals already made in the current free-allowance period of one card."""

    count: int = Field(ge=0)
    eur: Decimal | None = Field(None, ge=0)
    fx_eur: Decimal | None = Field(None, ge=0)  # amount already exchanged into foreign currency


class Scenario(BaseModel):
    kind: Literal["cash", "purchase"]
    amount_eur: Decimal = Field(gt=0)
    country: str = Field(HOME, min_length=2, max_length=2)
    days: int = Field(0, ge=0)
    used: dict[str, Usage] = {}  # by wallet label or card id
    atm_network: str = "other"  # owner of the ATM; unstated = the dearest case
    operator_fee: dict[str, Decimal] = {}  # the ATM operator's fee by card network; empty = not asked
    merchant: str | None = None
    at: AwareDatetime | None = None  # when the transaction happens; default now
    held_eur: Decimal = Field(Decimal(0), ge=0)  # already held in the transaction currency: not exchanged

    @property
    def foreign_currency(self) -> bool:
        return self.country.upper() not in EUROZONE

    @property
    def currency(self) -> str:
        c = self.country.upper()
        return "EUR" if c in EUROZONE else "EEA_non_EUR" if c in EEA else "other"

    @property
    def region(self) -> str:
        c = self.country.upper()
        return "home" if c == HOME else "EEA" if c in EEA else "outside_EEA"

    @property
    def abroad(self) -> bool:
        return self.country.upper() != HOME

    def usage_for(self, label: str) -> Usage | None:
        return self.used.get(label) or self.used.get(label.partition(":")[0])


class CostLine(BaseModel):
    label: str
    components: dict[str, Decimal] = {}
    missing: list[str] = []
    total: Decimal | None = None
    source: str = ""
    quote: str | None = None
    notes: list[str] = []

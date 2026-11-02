from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

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
HOME = "DE"
NUMERIC_FIELDS = ("percent", "min_eur", "fx_percent", "atm_operator_fee_eur", "cash_interest_pa")


class Passage(BaseModel):
    id: str
    card_id: str
    file: str
    page: int
    text: str


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
    source_file: str
    source_page: int
    confidence: float = Field(ge=0, le=1)
    quote: str | None = None
    not_stated: list[str] = []

    @model_validator(mode="after")
    def numbers_come_from_quote(self) -> "FeeSchedule":
        stated = {f: getattr(self, f) for f in NUMERIC_FIELDS if getattr(self, f) is not None}
        if stated and not self.quote:
            raise ValueError("quote is required when any fee is stated")
        in_quote = set(find_numbers(self.quote or ""))
        for name, value in stated.items():
            if value not in in_quote:
                raise ValueError(f"{name}={value} does not appear in quote")
        return self


class Scenario(BaseModel):
    kind: Literal["cash", "purchase"]
    amount_eur: Decimal = Field(gt=0)
    country: str = Field(HOME, min_length=2, max_length=2)
    days: int = Field(0, ge=0)

    @property
    def foreign_currency(self) -> bool:
        return self.country.upper() not in EUROZONE

    @property
    def abroad(self) -> bool:
        return self.country.upper() != HOME


class CostLine(BaseModel):
    label: str
    components: dict[str, Decimal] = {}
    missing: list[str] = []
    total: Decimal | None = None
    source: str = ""
    quote: str | None = None

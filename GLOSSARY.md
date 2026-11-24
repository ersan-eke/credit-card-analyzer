# cardcost

Helps a person get the most out of the cards they already own: which of them is cheapest for the payment or withdrawal
they are about to make, from the banks' published fee documents.

## Language

**Bank**:
The issuer a user picks first in the wallet; publishes one or more price lists.

**Preis- und Leistungsverzeichnis**:
A bank's published price list for its accounts and cards (a PDF or a web page); the only source of fees. In English
text: "price list".
_Avoid_: Kosten- und Leistungsbericht, Preis-Leistungsbericht, Entgeltinformation, Entgeltaufstellung

**Source**:
Where a price list is fetched from: one URL per price list, recorded by the operator.

**Product**:
One card a price list prices separately (e.g. Revolut Premium, HVB Mastercard). An account model, status or plan inside
the price list is not a product but a **Fact** the product's rules are conditioned on. A product is named as the bank
prints the card, without the issuing unit, the part of the document or the account model; it has no name when the price
list prices exactly one card.

**Status**:
A condition the user meets at a bank that changes its prices (e.g. DKB Aktivstatus); a Fact, stated by the user, never
inferred.

**Catalog**:
All price lists the tool knows, maintained by the operator, not by the user.
_Avoid_: Corpus, uploads

**Wallet**:
The products a user says they own, picked from the catalog, with the Facts they set for each card. Only wallet products
are ever compared.
_Avoid_: My cards, portfolio

**Allowance**:
A number or amount of fee-free uses per period (e.g. 4 free withdrawals a month); how much is left depends on the user's
usage this period, asked per question and never assumed: unknown counts as used up.

**Rule**:
One priced event of a product under conditions: what it is called, which events (payment, atm, credit), when it applies (currency, region, country), its price, an optional allowance, and the quote it comes from. The most specific matching rule wins; a rule that stacks adds to it. No price means the document does not state it: the cost is unknown.

**Section**:
A stretch of a price list that holds prices and the headings needed to read them (a table's rows with its header, or
the lines under a heading). Built by code from the layout, never by the model. One extraction call reads one section
view: a table section gives one view per group of value columns with identical cells, any other section one view.

**Route**:
The event question a section view gets (cash, payment, credit or holding); chosen by keyword.

**Triage**:
The model call for a view with a price line no keyword explains; it names the routes to read.

**Fact**:
Something about the user that a Rule is conditioned on (account model, status, plan, main or partner card, age, monthly
incoming money, sign-up date, repayment mode) or a price the user gives where the document states none. Set once per
card in the wallet, never inferred; only the facts a card's rules declare are asked for, and a missing one is asked back
and saved. A cost that needs a fact the user has not given is unknown, with the fact named.
_Avoid_: Profile, setting

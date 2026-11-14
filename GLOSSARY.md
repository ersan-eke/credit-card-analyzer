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
One card or account type a price list prices separately (e.g. Revolut Premium, HVB Mastercard in the AktivKonto).

**Status**:
A condition the user meets at a bank that changes its prices (e.g. DKB Aktivstatus); stated by the user, never inferred.

**Catalog**:
All price lists the tool knows, maintained by the operator, not by the user.
_Avoid_: Corpus, uploads

**Wallet**:
The products (with status) a user says they own, picked from the catalog. Only wallet products are ever compared.
_Avoid_: My cards, portfolio

**Allowance**:
A number or amount of fee-free uses per period (e.g. 4 free withdrawals a month); whether it is left depends on the user.

**Rule**:
One priced event of a product under conditions: what it is called, which events (payment, atm, credit), when it applies (currency, region, country), its price, an optional allowance, and the quote it comes from. The most specific matching rule wins; a rule that stacks adds to it. No price means the document does not state it: the cost is unknown.

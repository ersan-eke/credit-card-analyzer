# Golden label changes (#22, decision 8)

Naming rule (GLOSSARY, Product): the card as the bank prints it, without issuing unit, document part or account model; no name when the list prices one card. Names taken from `catalog/docs/*.md`.

| Where | Old | New | Why |
|---|---|---|---|
| rules key, wallet, question product, ranking | `ing:VISA` / product `VISA` | `ing:VISA Card` | ING prints "VISA Card [Debitkarte]"; the bracket is the card class, dropped |
| wallet, question product | `c24:Smartkonto` / product `Smartkonto` | `c24` / no product | Smartkonto is an account model (a Fact); the list prices one card |
| wallet, question product | `dkb:Kreditkarte` / product `Kreditkarte` | `dkb:Visa Kreditkarte` | DKB prints "Visa Kreditkarte"; matches the rules key |

Not changed, needs the operator: questions and rankings for `dkb:Visa Debitkarte / mit|ohne Aktivstatus` and `hvb:HVB Mastercard AktivKonto`. The status and account model are Facts, and collapsing them to `dkb:Visa Debitkarte` / `hvb:HVB Mastercard` would make two ranking entries share one label. They need the wallet-facts mechanism in the scenario, not a rename.

Uses of the old labels outside the golden: only synthetic fixtures in `tests/` (own data, unaffected) and `evals/golden_rules_checklist.md` (heading, documentation).

Effect on `run_eval --golden evals/golden_real.json`: recall 0.00 / precision 1.00 unchanged; cost 0.50 -> 0.38 because the untracked old-format `catalog/fees.json` still carries the old labels; it is replaced by the next extraction.

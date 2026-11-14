# Fee rules from whole price lists — design

Status: draft for review · 2026-11-14

## Intent

A user picks the cards they own (the wallet), says what they want to do — pay in a shop, pay online, withdraw cash, at
home or abroad, in EUR or another currency — and gets their cards ranked by what that costs. The ranking is only as
good as the fees behind it, and extraction is the weak step: 0.36 on the real golden set against the 0.9 gate.

Two causes, both confirmed by reading all 16 price lists (findings summarised below):

1. **The fee form is too small.** `FeeSchedule` has one cash rule, one FX percent and one interest rate. Real price lists
   price by account model (HVB, 9 models), status (DKB Aktivstatus), plan (Revolut, N26, C24), ATM network, region ×
   currency, amount thresholds, allowances by count and/or amount per calendar or rolling month, stacked fees, and
   annual fees with waivers. The model answers "not stated" because the form has nowhere to put what it reads.
2. **The model often never sees the fee page, or sees it scrambled.** At ingest, retrieval with a generic query reaches
   the fee page for only 0.73 of questions. And `read_pdf` (pdfplumber + a column heuristic) scrambles tables: BBVA
   p.3 labels and values come out as separate columns, N26 p.1 prices detach from plan names, DKB's two price columns
   interleave, Hanseatic headers split from their tables.

The user decided: every quirk must count in the calculation, not just be shown.

## Pipeline

```
PDF ──► layout extractor (local, no LLM) ──► clean text with intact tables  (cached, reviewed in the PR)
                                                     │
                                                     ▼
                         LLM, once per price list (whole text, no retrieval)
                                                     │
                                                     ▼
                         rules in a fixed format, each with quote + page
                                                     │
                       code: schema check, every number in its quote, quote in the text
                                                     │
                       human: pull request review (ADR 0002)
                                                     │
                       code: calculator evaluates rules for the wallet + question
```

Each stage does only what it is best at. Reading layout is mechanical (local tool). Turning German fee wording,
footnotes and column headers into rules needs language understanding (LLM) — no rule-based local tool can do that across
banks, and future cards must work without code changes. Validation and all money maths are code. The user's two-step
idea ("price list → JSON, then normalise") maps onto this: the extractor is step one, the fixed rule format plus code
validation is the normalising; a second LLM call would add a failure point and no capability.

## Goals

- Real golden set extraction ≥ 0.9 (existing gate), with cost and ranking scores kept.
- Every catalog card gets fees; a future price list needs no code change, only a review.
- All cost-relevant quirks found in the catalog are expressible and calculated (list below).
- Ingest is cheap and fast: no embedding model, one LLM call per changed price list.

## Non-goals (v1)

- **Multi-user accounts.** This design stays single-user: one wallet, as today (CLI, MCP, local API). Wallet facts
  (age, income, status) are stored in that wallet. User accounts — authentication, authorization, per-user wallets,
  encryption of personal facts at rest — are a separate project with its own design, brainstormed after this one
  (user decision). This design must not block it: wallet facts live in one place behind the wallet functions, not
  scattered through CLI/API code.

- Card replacement, PIN letters, shipping, top-up fees, transfers, insurance, cashback/rebates, emergency cash,
  paper statements. They are rarely what a user asks "which card should I use" about. The format must not preclude
  them, but neither the prompt nor the calculator covers them in v1. *(My call — the user said "include other costs like
  card payment"; payments are in.)*
- Live data (Revolut's exchange rate, "shown in the app" fees) — those are user-provided values, see below.
- OCR of scanned PDFs: all 16 have a text layer. The extractor bake-off notes whether a candidate could add OCR later.

## Anti-goals

- **A number in the fees file that the price list does not state.** Unknown stays unknown and ranks last; never 0.
- An LLM anywhere in the money maths, or at question time for fees.
- Per-bank code paths. A bank's quirk is data (rules), not an `if bank == ...`.

## Stage 1 — layout extraction (decided by bake-off, first task)

Every PDF in `catalog/docs` (and every future one) goes through the chosen extractor at ingest. Output: one text file
per price list, page markers kept, tables as Markdown tables (rows stay rows), cached under a name tied to the PDF's
sha256 so it is only rerun when the PDF changes. The LLM sees only this text; quotes are checked against it; the PR
shows it so the reviewer reads what the model read.

**Bake-off.** Candidates: Docling (MIT; layout + TableFormer model, CPU, `do_ocr=False`), PyMuPDF4LLM (no model, fast;
AGPL — acceptable, user decision), MinerU (strong on tables; AGPL or more permissive is acceptable, anything stricter
is not), and today's `read_pdf` as baseline. Marker is
excluded (GPL; model weights restricted for commercial use). Run all on the 16 PDFs and compare:

1. **Number preservation**: every number in the PDF's raw text layer (pdfplumber `extract_words`) appears in the
   output. Missing numbers = dropped content.
2. **Table fidelity** on the known bad pages — BBVA p.3, N26 p.1 and p.3–4, DKB p.1–2 (Standard vs Aktivstatus
   columns), Hanseatic both, HVB p.5 and p.8: is each value in the same row as its label and under its column header?
   Checked by eye against the PDF; the subagent catalogue gives the expected pairings.
3. Runtime for all 16 on a laptop CPU, install size, license fit (the weekly refresh runs in a GitHub Action).

Decision recorded as an ADR. Pick the simplest candidate that passes 1 and 2 on all 16.

**Permanent guard** (whichever wins): the number-preservation check runs at every ingest; a price list that fails it is
not sent to the LLM and is flagged in the refresh PR/issue, so a new card's bad extraction is caught before it costs a
wrong fee.

## Stage 2 — LLM extraction

- One call per price list with the whole extracted text (1k–27k tokens today; HVB largest). No retrieval at ingest;
  the embedding model is not loaded. Guard: a text above a set token budget fails loudly instead of being truncated.
- Output via the strict tool schema of the rule format (below); existing retry-with-error loop and
  `needs_review` handling stay.
- Model: Haiku by default. Accuracy depends on the input, so **prompt engineering is explicit work**, measured on the
  golden set, not guessed: system prompt explaining the rule format with worked examples taken from real catalog
  wording (allowance "whichever first", status columns, stacked "zzgl.", amount thresholds, footnote references like
  "1J"), instruction to walk products and price columns before writing rules, and the tool schema descriptions.
  Each prompt change bumps `PROMPT_VERSION` and is scored, with the score history kept so progress is visible. The
  goal is to get the most out of Haiku. Switching to a larger model is the user's decision: if Haiku plateaus below
  the gate, the builder stops and reports the scores and what is still failing; it does not switch models.
- Quote check: each rule's quote must appear verbatim (whitespace-squashed) on its page of the extracted text, and every
  number in the rule must appear in its quote (existing invariant, moved to the rule level).

## The rule format

A price list yields **products**: one per card the bank sells (HVB Mastercard, DKB Visa Debit, Revolut Premium). Account
model, status and plan inside a price list are **not** separate products; they are facts the rules are conditioned on
(HVB Mastercard is one product whose rules carry `facts: {account_model: [...]}`). The user sets them once per card in
the wallet, which replaces today's "which product do you mean?" ask-back for these cases; the ask-back remains for
wallet entries that match several cards. This reverses the per-status products of commit 7c04e44. *(My call: it keeps
the product count honest and puts the user's situation where the user sets it.)* A product is a list of **rules**.
Each rule is one priced event under conditions:

| Part | Content |
|---|---|
| `event` | `payment`, `atm`, `counter_cash`, `holding` (recurring card fee), `credit` (interest terms) |
| `when` | any of: `currency` (`EUR` / `EEA_non_EUR` / `other`), `region` (`home` / `EEA` / `outside_EEA`, plus `eurozone_country` where the bank words it by country, as ING does), `network` (ATM owner: `own` / named group like `UniCredit Group`, `Cash Group` / `other`), `merchant` (`gambling`), `weekend` (window stated by the bank), `amount` range (`min`, `max`, e.g. "unter 50 EUR"), `facts` (user fact conditions, below) |
| `price` | `percent`, `flat_eur`, `min_eur`, `max_eur` — any combination; `null` + listed in `not_stated` if the document does not give it |
| `allowance` | optional: `count`, `amount_eur`, `period` (`calendar_month` / `rolling_month` / `year`), both limits = whichever is reached first; price applies beyond it |
| `stacks` | `true` if this rule adds to the matching base rule ("zzgl. 2,20 %"), otherwise the most specific matching rule replaces broader ones |
| `holding` specifics | `per` (`month` / `year`), waiver conditions as `facts` (e.g. income ≥ 1000, age < 28) |
| `credit` specifics | `rate_pa`, `interest_free_days`, `interest_free_excludes` (e.g. cash) |
| provenance | `quote`, `page`, `confidence` |

Specificity: when several non-stacking rules match, the one with the most `when` conditions wins; a tie is an
extraction error (raised for retry/review).

### User facts

Rules reference **facts** by name; the product declares which facts it needs, so the app asks only for those.

- **Per card, set once in the wallet** (static): account model, status, plan, main vs partner card, age, monthly
  incoming money where a waiver depends on it, sign-up date where prices are grandfathered, Revolut legal entity (DE/LT
  IBAN), withdrawal limit, repayment mode (pays in full / instalments), and **user-provided values** for anything the
  document leaves open (missing interest rate, "shown in the app" fees). A user value is used in the calculation and
  marked as the user's, not the bank's.
- **Per question** (dynamic): event, amount **in EUR** (the user gives the EUR equivalent of a foreign-currency amount,
  as today; percent fees are taken of it — ING states "auf den Betrag in Euro", and no document gives a rate the tool
  could use; *my call*), currency, country, days until repayment for credit, the ATM operator's fee **per card network** (e.g. 3.50
  for Mastercard, 0 for Visa — each card picks its network's value), this period's usage counters (withdrawals,
  amount withdrawn, amount exchanged), and whether the transaction currency is already held (Revolut).

Facts the user has not given: allowance usage counts as used up (current behaviour); any other missing fact makes the
cost unknown with the fact named, so the app can ask back.

## Calculator

`calc.py` evaluates a product's rules for a scenario: select rules matching event and `when`, resolve specificity,
apply allowance against usage, add stacked rules, add the per-network operator fee, interest for credit by repayment
mode. Interest is simple interest `amount × rate_pa × days / 365` (as today) over the question's `days`: with
"pays in full", purchases inside `interest_free_days` cost 0 and anything in `interest_free_excludes` (cash) accrues
from day one; with "instalments", everything accrues. No minimum-repayment schedule in v1. *(My call.)* Decimal only,
rounding as today. `rank` keeps its policy: unknown cost last, never treated as free. `matrix`
keeps working on top of `rank`.

Holding fees are a cost of owning, not of a transaction, so the per-transaction ranking leaves them out and the
product view shows them. Spend-dependent waivers (BBVA monthly fee waived above 500 € spend, HVB annual-spend tiers)
could make a transaction lower a fee; v1 shows them, does not credit them. *(My call — flag if wrong.)*

## Golden set

`evals/golden_real.json` is rewritten in the rule format: per product, the expected rules (with quote and page), drafted
by Claude from the extracted text and the subagent catalogue, then corrected by the user card by card. The questions,
scenarios and expected costs stay where still valid; scenarios gain the new per-question inputs where needed (operator
fee per network, facts). New questions cover the quirks: account-model pricing (HVB), amount thresholds (Consorsbank,
BBVA, Trade Republic), rolling vs calendar allowance (Revolut, N26), stacked FX (DKB counter cash), network-specific
operator fee.

Scoring: extraction is scored on both sides so wrong fees cannot hide behind found ones. **Recall** = expected rules
found with equal values / expected rules; **precision** = extracted rules that match an expected rule / extracted rules
(within v1's events). The gate is both ≥ 0.9. A rule matches on product + event + values, and on `when` by meaning,
not spelling: two `when`s match if they select the same cases over the golden scenarios plus a fixed grid of
event × currency × region × network × amount boundaries (so ING's country wording and `region EEA + currency EUR`
match when they price the same transactions). *(My call.)* Cost and ranking scores as now.
Retrieval and context-recall metrics are dropped — ingest no longer retrieves. The synthetic `samples/` set moves to the
rule format too.

## What changes in the codebase

- `ingest.py`: `read_pdf` replaced by the chosen extractor; number-preservation check; cached text per sha256.
- `fees.py`: `fee_passages`, `FEE_QUERY` and the `Retriever` at ingest go; `update_fees` sends the whole text.
- `extract.py`: new prompt, new tool schema, quote check per rule against the extracted text.
- `models.py`: `FeeSchedule` → product with rules; `Usage`/`Scenario` gain the new inputs; wallet entries gain facts.
- `calc.py`: rule evaluation as above.
- CLI, API, MCP, advisor: wallet facts set once per card; per-question inputs (operator fee per network).
- `retrieval.py` and the `sentence-transformers`/`rank-bm25` dependencies: delete if nothing else uses them after this
  change (builder checks callers, e.g. `answer.py`).
- Evals and tests updated; `catalog/fees.json` and `samples/fees.json` regenerated (the current uncommitted partial
  files are not committed).
- ADR: new ADR superseding 0001's last sentence (layout extraction + whole-list extraction, no retrieval); ADR for the
  extractor choice; ADR 0002 unchanged. `GLOSSARY.md`: add **Rule**, **Fact**; update **Product**, **Allowance**.

## Build order

1. Extractor bake-off → ADR → wire into ingest with the number-preservation guard.
2. Rule format, calculator, unit tests (hand-built rules for each shape in the catalogue).
3. Golden set draft in the rule format → user review.
4. Prompt + extraction on the whole text; iterate prompts on the golden set until ≥ 0.9.
5. Wallet facts and per-question inputs in CLI/API/MCP.
6. Re-extract the catalog → PR for review.

## Left to the builder

Exact field names and JSON shape of rules; the token budget value; where cached text lives; how the CLI asks for
facts; how specificity ties are reported; test layout.

## Reference: shapes found in the 16 price lists

Recurring fee per month/year, waived by income/age/spend or by account model · percent · flat · flat + percent ·
percent with min (and max) · fee depends on account model / status / plan / sign-up date · ATM network (own, group,
other) · region × currency matrix · amount threshold switches price · N free per calendar or rolling month, or X € free,
or whichever first · FX allowance then percent · stacked "zzgl." fees · merchant (gambling) surcharge · interest with
interest-free period excluding cash · product only available with certain accounts · unquantified operator fee.
Weekend FX markup (Revolut Standard/Plus) and held-currency rules are in v1: `when.weekend` (the bank's window, e.g.
Fri 17:00–Sun 18:00 New York) evaluated from the question's time (default: now), and "currency already held" as a
question input.

# Handoff: ticket #22, prompt work on Haiku to the gate

State on 2026-11-20, branch `main`, last commit `719ef76`. Ticket: ersan-eke/credit-card-analyzer#22 (parent #16;
blocks #23). Read `GLOSSARY.md`, `docs/adr/0003`, `0004` and the "Model" part of
`docs/superpowers/specs/2026-11-14-fee-rules-design.md` first.

**Goal.** Extraction recall and precision both >= 0.9 on `evals/golden_real.json` with Haiku, or a report of scores and
remaining failures if Haiku plateaus. Each prompt change bumps `PROMPT_VERSION` and is scored; the score history is
kept. No model switch without the operator (see "Open decisions").

**Nothing is measured yet beyond the baseline.** `extract-v7` on all 16 real lists scored recall 0.01, precision 0.01
(6 lists returned nothing). Its raw responses were never saved (ingest has no cache path), so its failures cannot be
analysed offline. The v8 prompt below has never completed a live run.

## Working tree (uncommitted, 188 tests pass)

- `src/cardcost/extract.py`: `PROMPT_VERSION = "extract-v8"`. Prompt: six worked examples from real wording,
  `when` fields explained (amount, network, merchant, weekend, facts), zero prices in the unit the fee is stated in,
  shorter verbatim quotes, product naming. Tool schema: `when` gained `amount`, `network`, `merchant`, `weekend`; its
  list fields are plain arrays (empty = unset) because Anthropic strict mode allows at most 16 union-typed
  parameters (the first v8 attempt got a 400 with 22).
- `src/cardcost/models.py`: `When` drops empty lists before validation; `weekend: false` means no window.
- `evals/run_eval.py`: `--fees FILE...` scores a scratch fees file instead of `samples/` + `catalog/`.
- Untracked and not ours to touch: `catalog/fees.json` (old format, scores 0 against the rule golden) and
  `catalog/fees_nemotron.json`.

## Findings that shape the work

1. **Control characters in the converted text.** `catalog/docs/ing.md` (23), `hvb.md` (24 + 80) and `consorsbank.md`
   (24 + 5) contain `\x07` and `\x08`, e.g. `| \x07Auf den Betrag in Euro 2,20 % ...`. They are invisible, so quotes
   look verbatim but fail the check (`_squash(quote) in page`) because the model cannot copy them. ING, HVB and
   Consorsbank are among the lists that returned nothing in v7 ("quote not found verbatim"). This is a reader bug, not a
   prompt problem. Five golden ING quotes (`ing.atm.euro`, `ing.atm.eea`, `ing.atm.other`, `ing.pay.eea`,
   `ing.pay.other`) fail for the same reason; the price list does contain them. `ing.pay.eea` also has a real typo:
   golden starts "auf den Betrag", the page has "Auf den Betrag".
2. **Truncation is probably not size.** Haiku 5.5 allows 128k output tokens; our cap is 16000. A correct ING answer is
   about 7 rules, HVB about 10. v7's ING log showed the same rule name three times. Suspects, in order: prose before
   the tool call (`tool_choice: auto` plus "walk the document first"), repetition inside the rules array, thinking
   blocks (the model supports adaptive thinking and can disable it; whether it is on by default is unverified).
   Non-streaming requests above about 21k `max_tokens` are refused by the SDK, so raising the cap needs streaming.
3. **No `temperature` is sent**, so extraction runs at the default 1.0. It is part of the cache key.
4. **`extract_fees` retries on `max_tokens`**, so a truncated list costs two 16k calls with the same settings.
5. **Scorer.** A price of 0 written as `percent` and as `flat_eur` counts as different. v7's prompt told the model to
   use percent "0" while the golden uses `flat_eur` "0" (30 of 31 zero prices). Precision is 1.0 when nothing was
   extracted (`rule_score.py`, `if n_got else 1.0`). Products the golden does not cover (ING girocard, HVB UniCredit
   Card, UniCredit Card Business, girocard, Visa Infinite, maybe more at Consorsbank and DKB) count as extras.
6. **Golden labels are inconsistent.** Rules use `ing:VISA`, `dkb:Visa Kreditkarte`, `hvb:HVB Mastercard`; the questions
   use `dkb:Kreditkarte`, `c24:Smartkonto`, `hvb:HVB Mastercard AktivKonto` (account models are facts, not products).
   The model emits "VISA Card [Debitkarte]", "Revolut Plus-Karte (Revolut Bank UAB, ...)", "GoldCard".
7. **Lists by the same bank are near-duplicates** (5 Revolut lists, 2 Hanseatic). A worked example from one leaks into
   all of them, so example contamination is tracked per bank, not per list. 16 lists are 11 banks, 91 rules.
8. Cost of a full run (v7): 23 calls, about 415k tokens in, 212k out, about 10 minutes. `.env` has no prices
   (`CARDCOST_PRICE_*` empty), so cost is not logged in euros.

## Decisions (operator, 2026-11-20)

| # | Decision |
|---|----------|
| 1 | Schema changes count as prompt work (schema and prompt are one version). Golden rules are never edited to raise a score; suspected golden errors are reported with quote and page. |
| 2 | Every live response is recorded (`evals/runs/<version>.json`, not committed); analysis, re-validation and re-scoring happen offline. **The operator is consulted before every live run.** |
| 3 | At most 6 full runs; stop when two consecutive runs gain < 0.02 on both recall and precision, then report. No model switch (see Open decisions). No per-card spot runs except a regressing card. |
| 4 | Temperature 0 for extraction. |
| 5 | Rules used as prompt examples are flagged `used_as_example` in the golden, and scores are reported with and without them, plus without every bank that supplied an example. |
| 6 | Suspected golden errors are reported, never silently fixed. |
| 7 | Truncation: compaction first (one rule for several events, short quotes, no repeats), then `max_tokens` (needs streaming above about 21k). No split per product without the operator. |
| 8 | Product naming: named as the bank prints the card, without issuing unit, document part or account model; no name when the list prices exactly one card. Already in `GLOSSARY.md`. Apply it to the golden labels in one reviewable commit with an old -> new table. |
| 9 | Scorer treats a zero price as equal in either unit (`percent 0` = `flat_eur 0`), only when no minimum above 0; every other price stays strict. |
| 10 | **Holdout, chosen with care** (operator, 2026-11-20). Hold out whole banks, never single lists: lists of one bank share wording (5 Revolut lists, 2 Hanseatic), so a held-out list next to a developed one is not held out. Holdout = **DKB, N26, ING** (3 lists, 30 of 91 rules): none supplied a prompt example, and they cover three different shapes (status columns, plan columns, currency/region tiers with thresholds). Their rules are never read for error analysis and never used as examples; only aggregate recall/precision and failure counts per class are looked at, and only the control-character reader bug (finding 1) and the labels (decision 8) touch them. Everything else is the dev set (HVB, Consorsbank, C24, BBVA, Revolut x5, Hanseatic x2, TF Bank, Trade Republic: 13 lists, 61 rules). The gate stays on all 16; every score line reports all, dev and holdout. If holdout lags dev by more than 0.05, the prompt is overfitted: report that and stop tuning. Later, 2-3 new banks with independently drafted expected rules (two LLMs from different families, operator reviews only the disagreements) back the final claim. |
| 11 | Free offline checks before run 1 (see Plan step 4). |
| 12 | Score history `evals/prompt_scores.md`: one row per version with recall, precision, scores without example rules, failure counts per class, plus golden hash, schema hash, temperature, tokens, lists that returned nothing. Predictions per failure class are written before each run. |
| 13 | Golden gets `scored_products`; precision counts only those. The scorer prints labels extracted but not in the golden and golden labels never extracted. |
| 14 | No retry on `max_tokens`: record the list for review without a second call. |
| 15 | `tool_choice: any`, and drop "walk the document first"; if accuracy drops, bring it back as a short capped schema field. |
| 16 | Every score line also prints how many lists returned nothing. |
| 17 | Before the full run: a hand-written ideal answer passes `_parse`, then one live call on `revolut_standard`, cached, shown to the operator. |
| 18 | **Larger model, diagnostic only** (operator: yes). After the Haiku work, one run of the final prompt with `claude-sonnet-5-5`, outside the 6-run budget, operator OK first. It tells whether a miss is the model or the golden/scorer. The operator then decides whether extraction gets its own model setting; no switch before. |
| 19 | The `ing.pay.eea` golden quote typo (`auf` -> `Auf`) is fixed (operator: ok); it is a quote-only edit, price and `when` unchanged. |

## Open decisions (ask the operator)

- Whether extraction gets its own model setting (today one `CARDCOST_MODEL` serves all calls): decided only after the
  diagnostic Sonnet run (decision 18). Until then Haiku stays.

## Plan, in order

1. **Strip control characters** (`\x00-\x08`, `\x0b-\x1f`, not `\n`, `\t`) from the pages `read_text` returns, cached
   or fresh, so prompt, quote check and golden see the same text. Do not bump `READER_VERSION` (that reconverts all
   PDFs with Docling). Test: a page with `\x07` yields text a clean quote matches. Check the 16 golden lists afterwards:
   every golden quote verbatim on its page (expect only `ing.pay.eea` left), then fix its `auf` -> `Auf` (decision 19)
   and rerun the check until all 91 pass. Fix this first: it may by itself unblock ING, HVB and Consorsbank.
2. **Labels.** First grep every use of card/product labels (golden rules and questions, `tests/`, `advisor`, wallet
   facts); that grep has not been done. Then relabel the golden per decision 8 in its own commit with the table.
3. **Scorer and eval** (`evals/rule_score.py`, `evals/run_eval.py`): decisions 5, 9, 13, 16; history file per 12.
   Tests beside `tests/` for each.
4. **Offline gates**, no API: every golden rule passes `Rule(**d)`; the v8 schema has <= 16 union-typed parameters; a
   hand-written answer built from the golden passes `extract._parse`; token estimate per list against
   `MAX_INPUT_TOKENS`.
5. **Request and code**: temperature 0 and `tool_choice: any` in `extract_fees`, no retry on `max_tokens`
   (log it separately), cache path per prompt version. Update `tests/test_extract.py`.
6. **Flag example rules** in the golden (`used_as_example`): `revs.atm`, `bbvad.atm.big`, `bbvad.atm.small`, the C24
   ATM rules of the Pluskonto/Maxkonto group, `revs.weekend`, `bbvac.atm`, `gc.atm.home`, `gc.fx`, `gc.gambling`.
   Contaminated banks: Revolut, BBVA, C24, Hanseatic. Keep the list in step with the prompt. Also tag each golden
   label with its split (`dev` / `holdout`, decision 10) and make the eval print recall and precision for all, dev and
   holdout. Examples are only ever taken from dev banks.
7. **Probe**: one live call on `revolut_standard`; read content block types and order, `usage.output_tokens`,
   `stop_reason`. Show the operator. Write predictions per failure class (a schema gaps, b labels, c truncation and
   quotes, d wrong content) with expected recall/precision, wait for the OK, then run all 16.
8. **Iterate** per decisions 2-3 and 12: each run = one version, predictions first, operator OK first, analysis offline
   from the recorded responses, one change set per run. After the last version rerun it once for a noise estimate.
9. **Diagnostic larger-model run** (decision 18): the final prompt once with `claude-sonnet-5-5`
   (`CARDCOST_MODEL=claude-sonnet-5-5`, fresh output file and cache), after the operator's OK. Record it in
   `evals/prompt_scores.md` as a model row, not a prompt version. Report: which Haiku misses it fixes (model limit) and
   which it shares (golden or scorer suspects).
10. **Finish**: if >= 0.9 / 0.9 (all, and holdout within 0.05 of dev), commit with the history; if not, report scores,
    remaining failures per class and the suspected golden errors, and stop. Then `code-review`, commit to `main`.

## Running live

The shell has `ANTHROPIC_BASE_URL` set to a proxy; unset it and load `.env` for the process only (`.env` holds the key
and `CARDCOST_MODEL=claude-haiku-5-5`; never print it):

```bash
(unset ANTHROPIC_BASE_URL; set -a; . ./.env; set +a; CARDCOST_DB=/tmp/x.db uv run cardcost ingest --fees out/vN.json)
uv run python evals/run_eval.py --golden evals/golden_real.json --fees out/vN.json
```

`ingest` skips unchanged lists, so use a fresh output file per version.

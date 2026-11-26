# Extraction eval report: whole-document prompts (extract-v8 to v13)

Results on 2026-11-21, 343 tests then. All six budgeted full Haiku runs were used. Per-run analysis and predictions: `evals/prompt_scores.md`.

**Outcome: the 0.9 / 0.9 gate is not met.** Best Haiku run is v12 (all 0.19 recall / 0.73 precision). Sonnet 5.5 on the same
prompt reaches 0.39 / 0.47. Prompt wording alone will not close the gap; the failures are structural (below).

## Results

| Run | all (R/P) | dev | holdout | lists empty | missing/extra | tokens in/out |
|---|---|---|---|---|---|---|
| v8 | 0.09 / 0.29 | 0.13 / 0.30 | 0.00 / 0.00 | bbva c24 tfbank traderepublik | 91 / 22 | 415k / 21k |
| v9 inventory + event scope | 0.06 / 0.27 | 0.09 / 0.29 | 0.00 / 0.00 | c24 hvb ing | 94 / 16 | 354k / 36k |
| v10 conventions | 0.16 / 0.59 | 0.23 / 0.62 | 0.00 / 0.00 | bbva c24 ing | 84 / 11 | 376k / 58k |
| v11 inventory tags, no facts | 0.17 / 0.50 | 0.24 / 0.50 | 0.00 / 1.00 | c24 ing | 83 / 17 | 360k / 46k |
| v12 rules before confidence | 0.19 / 0.73 | 0.27 / 0.76 | 0.00 / 0.00 | c24 revolut_premium revolut_standard | 81 / 7 | 347k / 43k |
| v12 on claude-sonnet-5-5 (model row) | 0.39 / 0.47 | 0.47 / 0.45 | 0.20 / 0.67 | c24 consorsbank dkb hvb | 61 / 44 | 317k / 113k |
| v13 naming rule | 0.17 / 0.52 | 0.24 / 0.55 | 0.00 / 0.00 | c24 consorsbank revolut_standard | 83 / 16 | 360k / 36k |

Probe (revolut_standard, not a full run): one call, 18.5k in / 684 out, one `tool_use` block, no prose or thinking.
Predictions were written before each run; v8 predicted 0.55 / 0.60 and scored 0.09 / 0.29 (under-extraction was not foreseen).

## Findings

1. **Haiku collapse (class d, dominant).** In about half of the answers the `inventory` has 6-60 lines but `products` holds 1-5
   rules (consorsbank 23 -> 1, revolut_standard 30-38 -> 1, hvb 18-22 -> 1). Answers stop with `tool_use`, not truncation.
   Collapsed answers carry confidence 0.3-0.5. Moving `confidence` after `rules` (v12) cut extras 17 -> 7 but not the collapse.
2. **One bad rule rejects the whole list (class c).** `c24` fails on every version (number not in quote, quote not found);
   bbva, tfbank, traderepublik failed on some. `extract_fees` retries once, then the list goes to the review queue empty.
3. **Fees outside the five events** (card issuance etc.) came back with `event: []` and failed validation (v8); fixed by the
   v9 scope rule. The model still records plan subscriptions as `holding` rules.
4. **Conventions the model gets wrong without being told** (v10 fixed most): foreign-currency fee needs both currency
   values and both events; `network` invented; `counter_cash` added to plain cash; product named on single-card lists; facts
   for the one plan a list is for; credit (interest) rule skipped.
5. **Holdout (dkb, n26, ing) stays 0.00 recall on Haiku.** Labels explain part: the model names `dkb:Visa Debitkarte 1A` and
   `ing:VISA Card [Debitkarte]`. The v13 naming rule fixed the dkb label but not ing, and dkb recall stayed 0.00 (content
   mismatch). Holdout was only looked at as counts and the label diff.
6. **Noise is large.** Precision went 0.50 -> 0.73 -> 0.52 over v11-v13 on one-sentence prompt changes. The SDK has no
   `temperature` (see Code), so Haiku runs at the API default. Some "gains" of v10-v12 may be partly noise. The noise
   rerun of plan Task 6 was not run.
7. **Sonnet 5.5 (not the identical request: no forced tool).** Fixes 14 dev and 6 holdout Haiku misses and has none Haiku
   gets right that it misses. 37 dev / 24 holdout misses are shared (consorsbank 13, hvb 10, c24 6, revolut_plus 4,
   revolut_standard 4: validation failures, truncation, labels and facts). It thinks (a `thinking` block), writes 113k output
   tokens, and 3 of 17 answers hit `max_tokens` at 16000. Collapse 3 of 17. Scorer questions fail with `rules tie` on
   revolut_standard (two `cash_fee`) and tfbank (`interest`, `effective_interest`).
8. **Golden questions (reported, nothing changed):** no golden rule has the event `holding`, so every subscription the model
   records is an extra (revolut_plus 2.99, revolut_premium 7.99, revolut_ultra 60). The golden may leave plan prices out
   on purpose. No other suspected golden errors were found.

## Code changes made in this phase

- `evals/analyse_run.py` (+ `tests/test_analyse_run.py`): replays a recording offline through the real `update_fees`; a
  missing recording is "not recorded", never a call; holdout banks print counts and outcome class only. The `--fees`
  file must be fresh (an up-to-date file skips the replay). Use the model of the run in `CARDCOST_MODEL` (part of the cache key).
- `evals/rule_score.py`: an open amount bound (`{"max": None}`) is no bound (it crashed the scorer).
- `evals/run_eval.py`: `--record` now requires an existing `--runs` file (it appended an all-zero row for a run with no recording).
- `src/cardcost/llm.py`: the anthropic provider drops `temperature` (SDK 2.3.0 `Messages.create` has no such parameter, the
  request failed client-side); a 400 that names `tool_choice` as "not supported" is retried once without it and logged as
  `tool_choice_dropped` (Sonnet 5.5 rejects forced tools). The recording is cached under the forced-tool request's key.
- `src/cardcost/extract.py`: `PROMPT_VERSION = extract-v13`. Schema: required `inventory` (string array) before `products`;
  per product `product`, `rules`, `confidence` in that order. System prompt: inventory line format
  `<card> | <fee> | <price> -> <event or skip>`, one rule per non-skip line, the five-event scope rule, conventions
  (currency, network, counter_cash, null product, credit, no facts for a one-plan list), product names without footnote
  marker or bracket. Pinned by `tests/test_extract.py`. The inventory is ignored by `_parse`.
- The whole-branch review (fresh reviewer, 6d534de..1e650e0) found no Critical issue; its Important finding (silent, broad
  tool_choice retry) is fixed. Deferred minors: raise the `anthropic` floor in `pyproject.toml` from `>=0.40` to `>=2.3`;
  `analyse_run` shows "not recorded" when only the retry is unrecorded, has no test of `main()`, decides holdout by the id
  prefix before `_`, and uses the relative `catalog/docs`; `ruff` E501 on 3 lines of the SYSTEM prompt (rewrapping changes
  the recorded cache keys; whitespace is part of the key).

## How to run (the constraints still apply)

```bash
(unset ANTHROPIC_BASE_URL; set -a; . ./.env; set +a; CARDCOST_DB=/tmp/x.db \
  uv run cardcost ingest --fees out/vN.json --record evals/runs/extract-vN.json)
uv run python evals/run_eval.py --golden evals/golden_real.json --fees out/vN.json --record extract-vN --runs evals/runs/extract-vN.json
uv run python evals/analyse_run.py evals/runs/extract-vN.json --fees out/vN-replay.json   # offline, zero calls
```

- Ask the operator before every live call. Never print `.env`. Fresh `--fees` and `--record` files per version.
- Do not wrap a live run in `timeout`: a killed run keeps its finished lists (resume re-runs the same command), but it costs the operator turns.
- Never read holdout rules (dkb, n26, ing) for error analysis or examples; counts and the label diff only.
- `run_eval.py` prints every failure rule by rule, holdout included: filter the output (`grep -v " dkb\| n26\| ing"`) before reading.
- `evals/runs/` and `out/` hold all recordings of this phase; they are untracked. Recordings: probe, extract-v8 to v13.
  The Sonnet recording is `evals/runs/extract-v12-sonnet.json` (it was run before the history row was added by hand: row exists in `prompt_scores.md`).

## Open decisions for the operator

1. **Next step.** Recommended order by expected value: (a) drop only the failing rule instead of rejecting the whole list
   (code change in `extract_fees`: quote and number checks stay as the gate, the dropped rule goes to the review queue);
   (b) two calls, inventory first then rules for the inventory lines, or one call per page range (needs the operator's OK,
   handoff decision 7: no split without it); (c) the extraction model setting: Sonnet is about 2x Haiku on recall at about
   2.6x the output tokens, forced tool unavailable, truncation at 16000 (raise `max_tokens` or stream above about 21k).
2. **Noise rerun** of the final Haiku prompt (plan Task 6 step 1) to put an error bar on the 0.02 stop rule; about 350k in / 45k out.
3. **Golden:** should `holding` events be in? dkb Aktivstatus and hvb AktivKonto question labels were not renamed (need facts).
   The 14 `used_as_example` flags were not checked by the operator.
4. **Later:** 2-3 new independent banks with expected rules drafted by two LLMs from different families, to back the final claim.
5. The history `temp` column prints 0 although no temperature is sent on the anthropic provider.

# Ticket #22 offline foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Everything of ticket #22 that needs no API call: reader fix, golden labels and metadata, scorer views, eval output and history, offline gates, request settings. It ends before the first live call.

**Architecture:** The scorer keeps its per-event greedy match and additionally returns one hit record per expected and per extracted event; `tally()` aggregates them under a predicate (all / dev / holdout / without example rules / without example banks). The golden carries its own metadata (`holdout`, `scored_products`, `used_as_example`), so the eval reads everything from one file. Request settings live in `extract_fees`; recording lives in the cache file the existing `LLM` already supports.

**Tech Stack:** Python, pytest (`uv run pytest`), pydantic models in `src/cardcost/models.py`, no new dependency.

**Spec:** `docs/handoff-22-prompt-work.md` (decisions 1-19 and "Plan, in order"); background `docs/superpowers/specs/2026-11-14-fee-rules-design.md`, `GLOSSARY.md`, `docs/adr/0003`, `0004`. Handoff steps 7-10 (probe, live runs, Sonnet diagnostic, finish) are **not** in this plan: they need the operator's OK before every live call and depend on what the probe shows. Write that plan after Task 7.

## Global Constraints

- Golden rules are never edited to raise a score (decision 1). Allowed golden edits: the `ing.pay.eea` quote `auf` -> `Auf` (decision 19), labels per decision 8, and the metadata fields of Task 3. Price, `when`, allowance of a rule never change. Suspected golden errors are reported, not fixed (decision 6).
- Do not bump `READER_VERSION` (it reconverts every PDF with Docling).
- No live LLM call anywhere in this plan; tests use fakes. Never print `.env`.
- Holdout banks: `dkb`, `n26`, `ing` (decision 10). Their rules are never read for error analysis and never used as examples. Bank of a card id is `card_id.split("_")[0]` (`revolut_plus` -> `revolut`, `hanseatic_goldcard` -> `hanseatic`).
- Temperature 0, `tool_choice: {"type": "any"}`, no retry on `max_tokens` (decisions 4, 14, 15).
- Untracked `catalog/fees.json` and `catalog/fees_nemotron.json` are not ours: do not touch or commit them.
- Task 0 below commits the existing v8 working tree first, so later diffs are readable.
- Run `graphify update .` after the last task (project rule).

## Review Focus

- A zero price written `percent 0` vs `flat_eur 0` must compare equal, but `percent 0, min_eur 3` must not equal `flat_eur 0` (Task 4).
- A list that returns nothing must show as such, and must not look like precision 1.0 without a note (Task 5).
- Control characters inside a quote that the model could not copy must not make a quote fail (Task 1).
- A label extracted under a name the golden does not use must show up in the "extracted, not in golden" list, not vanish (Task 5).
- A response stopped by `max_tokens` must cost exactly one call (Task 7).

---

### Task 0: Commit the v8 working tree

**Files:** existing uncommitted `CLAUDE.md`, `GLOSSARY.md`, `evals/run_eval.py`, `src/cardcost/extract.py`, `src/cardcost/models.py`, `docs/handoff-22-prompt-work.md`.

- [ ] **Step 1:** `uv run pytest -q` must show 188 passed.
- [ ] **Step 2:** Commit exactly those files (not `catalog/fees*.json`, not `graphify-out/`, not `.claude/`): `git commit -m "Extraction prompt v8 (unmeasured baseline): worked examples, wider when schema, --fees in eval"`.

---

### Task 1: Strip control characters from the pages `read_text` returns

**Files:**
- Modify: `src/cardcost/ingest.py:115-129`
- Test: `tests/test_ingest.py`, `tests/test_golden.py`
- Modify: `evals/golden_real.json` (rule `ing.pay.eea`, quote only)

**Interfaces:**
- Produces: `read_text(path) -> list[str]` unchanged signature; its pages contain none of `\x00-\x08`, `\x0b-\x1f` (newline and tab kept), cached or fresh. Module constant `_CONTROL: re.Pattern`.

- [ ] **Step 1: Failing tests.**
  - `tests/test_ingest.py::test_read_text_drops_control_characters`: `tmp_path/"a.pdf"` with bytes `b"x"`; write `a.md` whose first line is the header `<!-- cardcost text: sha256={sha256 of the bytes} reader={READER_VERSION} -->` followed by `<!-- page 1 -->\n| \x07Auf den Betrag 2,20 %\n`; assert `read_text(path) == ["| Auf den Betrag 2,20 %"]`.
  - `tests/test_golden.py::test_golden_quotes_are_verbatim` parametrized over `(label, rule)` of `golden_real.json`: pages = `read_text(ROOT/"catalog/docs"/f"{label.partition(':')[0]}.pdf")`; assert `1 <= rule["page"] <= len(pages)` and `_squash(rule["quote"]) in _squash(pages[rule["page"]-1])` (`_squash` from `cardcost.extract`).
- [ ] **Step 2:** `uv run pytest tests/test_ingest.py tests/test_golden.py -k "control or verbatim" -q`. Expected: the control test fails, and the verbatim test fails for `ing.atm.euro`, `ing.atm.eea`, `ing.atm.other`, `ing.pay.eea`, `ing.pay.other` (verified 2026-11-20 against the committed cache).
- [ ] **Step 3: Implement.** `_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f]")`; apply `_CONTROL.sub("", ...)` to every page on both the cached branch and the fresh branch of `read_text` (the written cache file may keep the characters; the returned pages never do).
- [ ] **Step 4:** Rerun. Expected: only `ing.pay.eea` still fails.
- [ ] **Step 5:** In `evals/golden_real.json` change the quote of `ing.pay.eea` from starting `auf den Betrag` to `Auf den Betrag` (only that word). Rerun the full `tests/test_golden.py`: all 91 quotes pass.
- [ ] **Step 6:** `uv run pytest -q`; commit "Reader: strip control characters from pages; fix ing.pay.eea quote case (#22)".

---

### Task 2: Golden labels per decision 8

**Files:**
- Create: `docs/superpowers/plans/2026-11-20-label-table.md` (old -> new table, written by this task)
- Modify: `evals/golden_real.json`, plus whatever the grep finds (tests, `advisor`, wallet facts)

**Interfaces:**
- Produces: golden rule labels (`card` or `card:product`) and question `card`/`product` fields that follow the naming rule in `GLOSSARY.md` (product = the card as the bank prints it, no issuing unit, document part or account model; no product when the list prices one card).

- [ ] **Step 1: Grep every use** of product labels: `grep -rn "Visa Kreditkarte\|Visa Debitkarte\|HVB Mastercard\|Kreditkarte\|Smartkonto\|VISA" tests src evals docs --include="*.py" --include="*.json"` and the `label =` construction in `evals/run_eval.py` and `advisor.py`. List the hits in the table document.
- [ ] **Step 2: Draft the table.** One row per distinct label in golden rules and questions: old label, new label, reason. Known inconsistencies: rules `ing:VISA`, `dkb:Visa Kreditkarte`, `hvb:HVB Mastercard`; questions `dkb:Kreditkarte`, `c24:Smartkonto`, `hvb:HVB Mastercard AktivKonto`, `dkb:Visa Debitkarte / mit Aktivstatus` / `ohne Aktivstatus`. Account models and statuses are facts, not products: those questions keep the card's product and carry the model in their scenario/facts as the existing wallet-facts code expects. Take names from what the price list prints (`catalog/docs/<card>.md`), not from the model's output.
- [ ] **Step 3: STOP for operator review of the table.** Do not edit the golden before the operator has seen it.
- [ ] **Step 4:** Apply the table to `evals/golden_real.json` only, plus any other file Step 1 listed. `uv run pytest -q` and `uv run python evals/run_eval.py --golden evals/golden_real.json` must give the same recall/precision/questions numbers as before the relabel (it is a rename only).
- [ ] **Step 5:** Commit alone: "Golden: product labels per GLOSSARY naming rule (#22)" with the table in the message body.

---

### Task 3: Golden metadata: holdout, scored products, example rules

**Files:**
- Modify: `evals/golden_real.json` (top level and rules)
- Test: `tests/test_golden.py`

**Interfaces:**
- Produces, in the golden file: `"holdout": ["dkb", "n26", "ing"]`; `"scored_products": [label, ...]` (one per golden rule label after Task 2); rule field `"used_as_example": true` on rules whose wording is used in the v8 prompt examples.

- [ ] **Step 1: Failing tests** in `tests/test_golden.py`:
  - `test_holdout_banks_supplied_no_example`: for every rule with `used_as_example`, its bank (`card.split("_")[0]`) is not in `holdout`.
  - `test_scored_products_are_golden_labels`: `set(scored_products) == set(golden["rules"])`.
  - `test_example_ids_exist`: the ids in `EXAMPLE_IDS` (below) are exactly the rules flagged.
- [ ] **Step 2:** Run; fail.
- [ ] **Step 3:** Add the fields. Flag these rule ids (handoff step 6): `revs.atm`, `revs.weekend`, `bbvad.atm.big`, `bbvad.atm.small`, `bbvac.atm`, `gc.atm.home`, `gc.fx`, `gc.gambling`, `c24.atm.eur.plusmax`, `c24.atm.fx.plusmax`. Before flagging, compare with the six worked examples in `extract.py` `SYSTEM` and fix this list to match them exactly (the prompt is the source; if the prompt used a rule outside this list, add it, and if that rule is in a holdout bank, stop and tell the operator). Rule ids are stable across Task 2 (only labels change).
- [ ] **Step 4:** `uv run pytest -q`; commit "Golden: holdout, scored products, example flags (#22)".

---

### Task 4: Scorer: zero prices, scored products, hit records, tallies

**Files:**
- Modify: `evals/rule_score.py`
- Test: `tests/test_rule_score.py`

**Interfaces:**
- Changes `_price(p)`: when `percent == 0` and `min_eur` is None or 0, the tuple is built with `percent=None` and `flat_eur = flat_eur if not None else Decimal(0)`. Every other price stays strict. (Decision 9.)
- New `class Hit(NamedTuple): label: str; rule_id: str | None; hit: bool`.
  - `Score.want: list[Hit]`: one per expected event atom; `rule_id` = expected id; `hit` = matched.
  - `Score.got: list[Hit]`: one per extracted event atom of a scored label; `rule_id` = id of the expected rule it matched, or None when unmatched.
- `score(expected, extracted, countries=(), scored: set[str] | None = None) -> Score`: extracted atoms of labels not in `scored` are left out of `got`, `extra` and the precision count (None = all counted). Existing fields keep their meaning; existing callers and tests still work.
- New `tally(s: Score, keep: Callable[[str, str | None], bool]) -> tuple[float, float]`: recall = kept hit wants / kept wants; precision = kept got hits / kept got; an empty denominator gives 1.0 (as today). `keep(label, rule_id)`.

- [ ] **Step 1: Failing tests** in `tests/test_rule_score.py` (reuse that file's rule-building helper):
  - `test_zero_price_equal_in_either_unit`: expected `{"percent": "0"}` vs got `{"flat_eur": "0"}` match; `{"percent": "0", "min_eur": "3"}` vs `{"flat_eur": "0"}` do not; `{"percent": "1"}` vs `{"flat_eur": "1"}` do not.
  - `test_unscored_label_is_not_an_extra`: one extracted rule under a label outside `scored` leaves precision 1.0 and `extra == []`; the same label inside `scored` gives precision 0.
  - `test_tally_excludes_example_rule_and_its_match`: two expected rules, one with id in an example set, both matched: `tally(s, lambda l, i: i not in examples)` has recall 1.0 over one want and the example's matching extracted rule is not in the precision denominator; an unmatched extracted rule (id None) stays in it.
  - `test_tally_by_bank`: `keep=lambda label, _: label.split("_")[0].partition(":")[0] in {"dkb"}` isolates one bank's recall.
- [ ] **Step 2:** Run; fail.
- [ ] **Step 3:** Implement as specified; the tallies reuse the matching `score()` already does (add the two lists in the existing loop, do not match twice).
- [ ] **Step 4:** `uv run pytest tests/test_rule_score.py -q`, then full suite; commit "Scorer: zero price in either unit, scored products, per-event hits, tally (#22)".

---

### Task 5: Eval output and score history

**Files:**
- Modify: `evals/run_eval.py`
- Create: `evals/prompt_scores.md` (header row only), `.gitignore` entry `evals/runs/`
- Test: `tests/test_eval_report.py` (new)

**Interfaces:**
- Consumes: `score`, `tally`, `Score` from Task 4; golden fields from Task 3.
- Produces in `evals/run_eval.py`:
  - `views(golden: dict, s: Score) -> dict[str, tuple[float, float]]` with keys `all`, `dev`, `holdout`, `no_examples`, `no_example_banks` (decision 5; "dev" = bank not in `holdout`; `no_example_banks` = bank not in the banks of example rules).
  - `label_diff(golden: dict, rules: dict) -> tuple[list[str], list[str]]`: (extracted labels not in the golden, golden labels never extracted) (decision 13).
  - `empty_lists(golden: dict, rules: dict) -> list[str]`: golden card ids (the part before `:`) with no extracted label (decision 16).
  - `history_row(version: str, golden_path: Path, views: dict, empty: list[str], tokens: tuple[int, int], extra: int, missing: int) -> str`: one Markdown table row: version, first 8 hex of sha256 of the golden file, first 8 of sha256 of `json.dumps(TOOL, sort_keys=True)`, `TEMPERATURE` (from `cardcost.extract`, added in Task 7; until then read it with `getattr(..., None)`), tokens in/out, the five views as `recall/precision`, empty count and ids, missing and extra counts, and an empty notes column.
- CLI: main prints the five views as lines `all   0.92 0.91`, then `N of M lists returned nothing: ids`, then the two label lists; the exit gate stays on `all`. New optional `--record VERSION [--runs FILE]` appends `history_row` to `evals/prompt_scores.md`; `--runs` is the recorded-responses file (Task 7) whose `usage` input/output tokens are summed for the row.

- [ ] **Step 1: Failing tests** in `tests/test_eval_report.py` using a 3-card inline golden and extraction dicts:
  - `test_views_split_holdout_and_dev`; `test_empty_lists_names_cards_with_no_label`; `test_label_diff_reports_both_sides`; `test_history_row_has_hashes_and_counts` (assert the row starts with `| extract-v8 |`, contains the 8-hex golden hash and the empty ids).
- [ ] **Step 2:** Run; fail.
- [ ] **Step 3:** Implement. `main` gets the golden's `holdout` and `scored_products` through `score(..., scored=set(golden["scored_products"]))` when the golden has that key (the synthetic `golden.json` has none: all counted). Create `evals/prompt_scores.md` with a heading, a line "Predictions per failure class are written here before each run", and the table header matching `history_row`.
- [ ] **Step 4:** `uv run python evals/run_eval.py --golden evals/golden_real.json` on the committed catalog: runs, prints the views, exits 1 as before (scores are low). `uv run python evals/run_eval.py` (synthetic golden) unchanged in exit code.
- [ ] **Step 5:** Full suite; commit "Eval: dev/holdout/example views, empty lists, label diff, score history (#22)".

---

### Task 6: Offline gates (decision 11)

**Files:**
- Test: `tests/test_extract_gates.py` (new)

**Interfaces:**
- Consumes: `extract.TOOL`, `extract._parse`, `extract.build_prompt`, `extract.MAX_INPUT_TOKENS`, `extract.CHARS_PER_TOKEN`, `ingest.read_text`, `models.Rule`.
- Test helper `golden_response(label) -> dict` in the same file: builds an Anthropic-shaped response `{"stop_reason": "tool_use", "content": [{"type": "tool_use", "name": "record_fees", "input": {"products": [...]}}]}` from the golden rules of one card, one product entry per label, `confidence` 1, converting each golden rule to the tool shape (drop `id` and `used_as_example`; `when.facts` dict -> list of `{name, values}`; empty `when` lists as `[]`, `weekend` false when unset).

- [ ] **Step 1: Write the tests** (they should pass on the current code; if one fails the failure is the finding, report it):
  - `test_every_golden_rule_is_a_valid_rule`: `Rule(**d)` for all 91 rules, `id`/`used_as_example` removed first if `Rule` forbids extras.
  - `test_schema_has_at_most_16_union_parameters`: count nodes of `TOOL["input_schema"]` that are `anyOf`, or whose `type` is a list; assert `<= 16`.
  - `test_golden_answer_passes_parse[card]` parametrized over golden cards: `_parse(card, f"{card}.pdf", golden_response(...), pages)` returns schedules, `pages = read_text(...)`. Holds only after Task 1.
  - `test_every_list_fits_the_token_budget[card]`: `len(build_prompt(file, pages)) // CHARS_PER_TOKEN <= MAX_INPUT_TOKENS` for all 16 PDFs in `catalog/docs`.
- [ ] **Step 2:** `uv run pytest tests/test_extract_gates.py -q`. If the union count exceeds 16 or a golden answer fails to parse, fix the cause in the schema or the converter helper (a schema change is prompt work: bump `PROMPT_VERSION` to `extract-v9` and say so in the commit), not by editing golden rules.
- [ ] **Step 3:** Commit "Offline gates for extraction: golden answers parse, schema within strict limit, lists fit (#22)".

---

### Task 7: Request settings and recording

**Files:**
- Modify: `src/cardcost/extract.py` (`extract_fees`, constants), `src/cardcost/cli.py` (`cmd_ingest`, ingest subparser at about line 204)
- Test: `tests/test_extract.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `extract.TEMPERATURE = 0`; the request `extract_fees` sends is `{"system": SYSTEM, "tools": [TOOL], "tool_choice": {"type": "any"}, "temperature": TEMPERATURE}`; `cardcost ingest --record FILE` builds `LLM(conn=conn, cache_path=Path(FILE))` (default None, behaviour unchanged).

- [ ] **Step 1: Failing tests** (use the file's existing `FakeLLM`; extend it to remember `kwargs` of each call):
  - `test_request_is_deterministic_and_forces_the_tool`: the call's kwargs have `temperature == 0` and `tool_choice == {"type": "any"}`.
  - `test_max_tokens_is_not_retried`: a fake whose first response has `stop_reason: "max_tokens"` is called exactly once; the result is `[]` and an extraction row with status `needs_review` and an error containing `max_tokens` is stored.
  - `test_invalid_answer_still_retries_once` (existing behaviour kept: first answer with a missing quote, second good).
  - In `tests/test_cli.py`: `ingest --record out.json` passes a `cache_path` to `LLM` (monkeypatch `LLM` with a recorder, as that file already does for other commands).
- [ ] **Step 2:** Run; fail.
- [ ] **Step 3:** Implement. In the retry loop, when `response.get("stop_reason") == "max_tokens"`: set `error` to `"response stopped with max_tokens"`, `log.warning("extraction_truncated", extra={"card": card_id})`, and `break` without a second call. `to_openai` ignores `temperature` for non-Anthropic providers; leave it, and note it in a one-line comment at `TEMPERATURE`.
- [ ] **Step 4:** Add `evals/runs/` to `.gitignore` if Task 5 has not. `uv run pytest -q` all green, `uv run ruff check .` if the repo uses it (it has `.ruff_cache`).
- [ ] **Step 5:** `graphify update .`; commit "Extraction request: temperature 0, forced tool, no retry on truncation, optional response recording (#22)".

---

## Done when

All tasks committed, `uv run pytest -q` green, `uv run python evals/run_eval.py --golden evals/golden_real.json` prints the five views plus empty lists and label diff. Next (separate plan, operator OK before each live call): probe on `revolut_standard`, predictions, first full run, iterate, Sonnet diagnostic, finish.

## Self-review notes

- Spec coverage: decisions 4, 5, 9, 10, 11, 12 (row; predictions stay manual in the history file), 13, 14, 15, 16, 19 and plan steps 1-6 map to Tasks 1-7. Decisions 2/3/17/18 and steps 7-10 belong to the live plan. Decision 2's recording is Task 7's `--record`.
- Handoff step order differs: offline gates (its step 4) are Task 6 because they need Task 1; flags (its step 6) are Task 3 because the scorer views read them.
- Open risk: if Docling-converted cache headers are stale for some PDF, `read_text` in tests would try to reconvert (needs `uv sync --extra ingest`); today the 16 caches are current.

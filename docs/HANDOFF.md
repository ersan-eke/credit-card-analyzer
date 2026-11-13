# Handoff: next session

State on 2026-11-13. Last commit `c716301`. 113 tests pass, ruff clean. Not committed: the user's review notes in
`evals/golden_real_sheet.md` (commit first: re-running `verify_golden.py > evals/golden_real_sheet.md` overwrites them),
`GLOSSARY.md`, `docs/adr/0001`, `docs/adr/0002`. Step 1 done: the 16 bank PDFs are in `catalog/docs/` with
sources in `catalog/sources.toml` (the 17th price list is Bank Norwegian, a web page, step 8).

Read `GLOSSARY.md` and `docs/adr/` first; use their terms (Preis- und Leistungsverzeichnis / price list, Bank, Source,
Product, Status, Catalog, Wallet, Allowance).

## Use case (decided 2026-11-13, replaces the earlier one)

Portfolio project that should feel like a real product: "get the most out of the cards you already own". At the ATM or
till, on a phone: amount, country, withdrawal or payment → which wallet card is cheapest, its fee, quote and page.

- Front door: a mobile web page (existing FastAPI app), hosted on the user's own server with Docker.
- Users never upload. The operator maintains a catalog of price lists (PDF or HTML), fetched from sources.
- Fees are extracted once per price list at ingest and reviewed (ADR 0001); the web page makes no LLM call.
- Only wallet products are compared. No "cheapest card overall" (decided against: the tool optimises what you own).
- Wallet picker: Bank → card / account model → status (e.g. DKB Aktivstatus). Saved in the browser, no account.
- Allowance usage is asked only when the answer changes the winner (one extra tap; "don't know" = used up).
- LLM free-text questions come later, with the user's own API key or a site key. CLI `ask` and the stdio MCP stay.

## Plan (each step test-first, one commit, pytest + both evals after each)

1. **Catalog layout and renames.** `catalog/sources.toml` (one `[[source]]` per price list: `id`, `bank`, `url`; type
   from the response content type), downloaded copies in `catalog/docs/` (PDF, or extracted text for HTML), committed.
   Move the 17 bank PDFs there; `samples/` keeps only alpha/beta/gamma. Look up each official source URL; list any not
   found for the user instead of guessing. Fix ids everywhere: `evals/golden_real.json` (42 refs), `tests/test_ingest.py`,
   `tests/test_advisor.py`, `evals/llm_cache.json` keys. Rename the old document name in README, PLAN, extract.py.
2. **Old HANDOFF tasks 1 and 4.** r04: only the part above the amount limit is charged (150 used + 100 → 2 % of 50 =
   1,00 €, min 1 €). Golden corrections: r04 → 1.00; r14 ("2,20 %") and r17 ("4") are fact questions (new expectation type
   in golden + `run_eval.py` + `test_golden.py`); r13/r18/r20 must ask about usage; r09/r10/r15 must ask for the HVB
   product; r19 correct (EU/EWR note). Extend the golden to the new banks (a few questions each).
3. **Extraction at ingest** → `catalog/fees.json` (reviewed fees, with quote, page/section, "Stand" date per source).
   Statuses as separate products (`DKB Visa / mit Aktivstatus`, `/ ohne`); check whether DKB already extracts them.
   Answers (CLI, MCP, API) read `fees.json`.
4. **User runs the live eval** (commands below) on the new path; numbers into the README, commit the cache, propose fixes.
5. **Cuts.** Delete the ingest webhook (HMAC, replay, path check) and the SQLite review queue + `review` CLI; keep the
   `agent_run` audit. Remove `GET /ask` from the public app. BM25 default; `sentence-transformers` becomes the optional
   extra `vector` (keeps PyTorch out of the image and the refresh job; eval still compares modes).
6. **Web page.** Wallet picker (fast, grouped by bank), question form (amount, last country preselected, withdrawal or
   payment), result with quote/page and "Stand". Usage question only when it changes the winner (old task 2: price
   allowance-left and used-up; differ → return a question; equal → answer).
7. **Revolut weekend surcharge** (+1 % FX at weekends, Revolut PDF): only if extractable with a quote; the web form knows
   the date. Otherwise list under README limits.
8. **HTML sources** (Bank Norwegian, `https://www.banknorwegian.de/preise-und-produkte/`): stdlib HTML parser → text →
   sections; quote cites URL + section heading.
9. **Weekly refresh Action.** Download each source, hash (extracted text for HTML), on change re-extract and open a PR
   with the fee diff (old/new value, quote, page). On failure keep old data and "Stand", open an issue (ADR 0002).
10. **Deploy and README.** `Dockerfile` (uv, no extras) + `docker-compose.yml` with Caddy (automatic HTTPS) on a
    subdomain of the user's (domain not chosen yet). Action on push to `main`: build, push to `ghcr.io`, SSH
    `docker compose pull && up -d` (SSH key as repo secret; rollback = previous image tag). README rewrite: link, GIF,
    eval table, ADRs, limits (bank PDFs are committed with source URLs; removed if a bank objects).

## Live eval (user runs it; never measured yet)

The project does not read `.env`, so export in the shell:

```bash
export CARDCOST_PROVIDER=openrouter
export CARDCOST_MODEL=anthropic/claude-sonnet-5.5   # exact id from openrouter.ai/models; must support tool calls
export OPENROUTER_API_KEY=sk-or-...
uv run python evals/run_eval.py --live --golden evals/golden_real.json
uv run python evals/run_eval.py --live
```

Answers are recorded in `evals/llm_cache.json`; replay needs the same provider and model (they are in the cache key).

## Interview talking points

LLM extracts with verbatim quotes, code calculates in Decimal (no invented numbers); BM25 beat vectors on the real
German documents (0.90 vs 0.60); extraction once at ingest, so the public page is instant and costs nothing per visitor;
fee changes arrive as reviewable PRs (human in the loop, GitHub as the UI); PDF and HTML through the same pipeline;
PDF text is untrusted (`<untrusted>` tags, read-only MCP, redaction before logging); the tool asks instead of guessing;
real layout problems fixed (HVB columns, ING kerning, Revolut vocabulary).

# cardcost

Answers "which of my credit cards is cheapest for *this* (e.g. 300 EUR cash in the USA)?" from the banks'
German *Kosten- und Leistungsbericht* PDFs: the LLM only reads the documents and writes the answer text, and all money maths is plain Decimal code.

```bash
uv sync && export ANTHROPIC_API_KEY=... CARDCOST_MODEL=claude-sonnet-5-5 && \
  uv run cardcost ask "Welche Karte ist am günstigsten für 300 EUR Bargeld in den USA?"
```

### Other providers

Set `CARDCOST_PROVIDER` to `google` (AI Studio key in `GEMINI_API_KEY`) or `openrouter` (`OPENROUTER_API_KEY`), and set
`CARDCOST_MODEL` to that provider's model id. Both go through their OpenAI-compatible `/chat/completions` endpoint
and are translated to the Anthropic response shape, so retry, audit, review and the LLM cache work the same.
The cache key includes the provider, so recorded answers from different providers don't mix.

```bash
CARDCOST_PROVIDER=google CARDCOST_MODEL=gemini-3.8-flash GEMINI_API_KEY=... uv run python evals/run_eval.py --live --mode hybrid
CARDCOST_PROVIDER=openrouter CARDCOST_MODEL=google/gemini-3.8-flash OPENROUTER_API_KEY=... uv run cardcost ask "300 EUR Bargeld in den USA"
```

## How it works

| step | module | LLM? |
|---|---|---|
| PDF → per-page text (tables as `cell \| cell` rows), NFC, ~200-word line windows, never across files | `ingest.py` | no |
| Hybrid retrieval per card: BM25 (indexed per card) + `multilingual-e5-small` embeddings, RRF k=60 | `retrieval.py` | no |
| Fee extraction via a strict tool schema into `FeeSchedule`; every number must appear in `quote`, the quote must be verbatim on the cited page; one retry with the error, then review queue | `extract.py` | yes |
| Cost = `max(amount·pct/100, min)` + FX (non-EUR) + ATM operator fee (abroad) + interest (`--days`), Decimal, half-up per component; unknown fee ⇒ no total, ranked last | `calc.py` | no |
| ≤3-sentence answer; every number in it must be in the computed table, else regenerate once, else a template | `answer.py` | yes |
| Audit: `agent_run` (prompt_version, model, tokens, cost_eur), `extraction`, `review` (one decision per extraction) | `db.py` | no |

PDF text is wrapped in `<untrusted>` tags and the system prompt says never to follow instructions inside them
(the Gamma sample contains such an injection). Logs are JSON with a per-question `run_id`. IBANs, emails and phone numbers
are redacted before anything is logged.

## Commands

```bash
uv run cardcost ingest [file.pdf ...]          # corpus = samples/ + data/private/ (gitignored) + webhook uploads
uv run cardcost products                       # card products found, e.g. beta_card:Beta Classic, beta_card:Beta Gold
uv run cardcost wallet alpha_card beta_card:Gold   # pick the account/card types you own (default: all)
uv run cardcost ask "Einkauf über 200 EUR in der Schweiz"   # flags: --amount --kind cash|purchase --country US --days 30
uv run cardcost matrix --countries DE,FR,US    # which card wins for which amount: "1-375 EUR -> alpha_card; 376-2000 EUR -> beta_card:Gold"
uv run cardcost review list
uv run cardcost review edited 7 --set min_eur=6,50 --quote "3,0 % mind. 6,50 EUR" --reviewer me   # used on the next question
uv run uvicorn cardcost.api:app               # GET /ask?q=..., POST /webhooks/new-document
```

**Webhook**: `X-Timestamp: <unix s>` and `X-Signature: hex(HMAC-SHA256(CARDCOST_WEBHOOK_SECRET, "<timestamp>.<raw body>"))`,
body `{"event_id": "...", "path": "data/private/x.pdf"}`. A request is rejected if it is older than 5 minutes, if its event id was already seen (it gets 200 and is not queued again), or if the path is outside `data/private/`.
The endpoint returns 200 and ingests in the background.

**MCP** (read-only tools `get_fee(card, amount_eur)`, `compare_cards(amount_eur, country)`):

```bash
claude mcp add cardcost -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY -e CARDCOST_MODEL=claude-sonnet-5-5 \
  -- uv run --directory "$PWD" cardcost-mcp
```

## Eval

`evals/golden.json`: 20 hand-checked questions over the 3 synthetic PDFs in `samples/`. They include 4 "not stated" questions, compound and umlaut terms, amounts on both sides of each minimum-fee crossover (200 / 250 / 750 EUR), and an injection test.
Each question's expected costs are written out in its `_hand` field. `evals/run_eval.py` scores the three steps separately:
retrieval (expected page in the card's top 3, 17 questions), extraction (exact Decimal match, null must be null) and
final ranking. Run it with `--live` once to record LLM answers into `evals/llm_cache.json`. CI then replays them without a key
and fails if hybrid extraction accuracy is below 0.9.

| mode | retrieval@3 | extraction | ranking |
|---|---|---|---|
| bm25 | 1.00 | _pending live run_ | _pending_ |
| vector | 0.94 | _pending_ | _pending_ |
| hybrid | 0.94 | _pending_ | _pending_ |

Retrieval@1: bm25 0.65, vector 0.65, hybrid 0.71. The remaining hybrid miss is q02 *"Ich hebe 300 EUR … ab"*: a separable
German verb ("hebe … ab" means "abheben", to withdraw), and neither side links it to "Bargeldauszahlung". Extraction does not depend on this question's retrieval,
because the advisor always adds a fixed fee-terms query.

## A failure the eval found

The first retrieval run gave BM25 0.82 @3, and q04 ("Wie hoch ist das **Fremdwährungsentgelt** der Alpha Card?") missed,
although that exact word is on page 2. The cause: BM25 was indexed over all cards, but search is filtered to one
card. "Alpha" and "Card" are rare corpus-wide, so pages repeating the card name outscored the fee term.
**Fix:** one BM25 index per card (IDF within the card's own pages). BM25 went from 0.82 to 1.00 @3. A unit test also caught that
zero-score BM25 passages were entering RRF in arbitrary order. They are now dropped before fusion.

## Limits

- Forced `tool_choice` returns a 400 on Sonnet 5.5 / Opus 5.5. The tool is `strict` with `tool_choice: auto`, and a missing
  call counts as a validation failure (retry, then review).
- The scenario parser is deterministic and small: it handles "N EUR", a fixed list of country names, and cash vs purchase keywords. Use flags for anything else.
- Each `FeeSchedule` has one `source_page`, so fees spread over several pages of one product validate only if the quote sits on that page.
- The FX fee is applied to non-EUR countries for both cash and purchases. The ATM operator fee is applied to cash abroad only. Interest uses simple act/365
  on the withdrawn amount.
- Reviewed values are keyed by card and product, not by document version. Re-ingesting a changed PDF keeps old corrections.
- Passages and embeddings are rebuilt per process, which takes a few seconds and only suits a handful of PDFs.
- The `matrix` command scans whole euros from 1 to `--max` instead of solving the crossovers analytically.
- The API has no auth. The MCP tools are read-only for callers but still write audit rows.
- On google/openrouter the Anthropic-only `strict` flag is dropped, so tool arguments are not schema-guaranteed. The Pydantic and quote
  checks still apply, and malformed arguments go through the retry-then-review path. Whether every model accepts the
  nullable `["string", "null"]` schema types is untested.
- The fee model has no free monthly allowance yet. Real price lists have rules like C24's "4 x 0,00 EUR, then 2,00 EUR"; today that
  can only become `min_eur=2.00` with the allowance noted in `conditions`.
- The golden eval covers the synthetic samples only. Real PDFs belong in `data/private/` (gitignored), with an optional private golden file.

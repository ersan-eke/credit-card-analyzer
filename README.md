# cardcost

Answers "which of my credit cards is cheapest for *this* (e.g. 300 EUR cash in the USA)?" from the banks'
German *Preis- und Leistungsverzeichnis* PDFs: the LLM only reads the documents and writes the answer text, and all money maths is plain Decimal code.

```bash
uv sync && export ANTHROPIC_API_KEY=... CARDCOST_MODEL=claude-sonnet-5-5 && \
  uv run cardcost ask "Welche Karte ist am günstigsten für 300 EUR Bargeld in den USA?"
```

### Other providers

Set `CARDCOST_PROVIDER` to `google` (AI Studio key in `GEMINI_API_KEY`) or `openrouter` (`OPENROUTER_API_KEY`), and set
`CARDCOST_MODEL` to that provider's model id. Both go through their OpenAI-compatible `/chat/completions` endpoint
and are translated to the Anthropic response shape, so retry, audit and review work the same.

```bash
CARDCOST_PROVIDER=google CARDCOST_MODEL=gemini-3.8-flash GEMINI_API_KEY=... uv run cardcost ingest --mode hybrid
CARDCOST_PROVIDER=openrouter CARDCOST_MODEL=google/gemini-3.8-flash OPENROUTER_API_KEY=... uv run cardcost ask "300 EUR Bargeld in den USA"
```

## How it works

| step | module | LLM? |
|---|---|---|
| PDF → per-page text (tables as `cell \| cell` rows), NFC, ~200-word line windows, never across files | `ingest.py` | no |
| Hybrid retrieval per card: BM25 (indexed per card) + `multilingual-e5-small` embeddings, RRF k=60 | `retrieval.py` | no |
| Fee extraction via a strict tool schema into `FeeSchedule`; every number must appear in `quote`, the quote must be verbatim on the cited page; one retry with the error, then review queue | `extract.py` | yes |
| Cost = `max(amount·pct/100, min)` + FX (non-EUR) + ATM operator fee (abroad) + interest (`--days`), Decimal, half-up per component; unknown fee ⇒ no total, ranked last. Free allowances (see below) can make the cash fee 0 | `calc.py` | no |
| ≤3-sentence answer; every number in it must be in the computed table, else regenerate once, else a template | `answer.py` | yes |
| Audit: `agent_run` (prompt_version, model, tokens, cost_eur), `extraction`, `review` (one decision per extraction) | `db.py` | no |

PDF text is wrapped in `<untrusted>` tags and the system prompt says never to follow instructions inside them
(the Gamma sample contains such an injection). Logs are JSON with a per-question `run_id`. IBANs, emails and phone numbers
are redacted before anything is logged.

## Commands

```bash
uv run cardcost ingest [file.pdf ...]          # extract changed price lists (default catalog/docs/) into catalog/fees.json; --fees to use another file
uv run cardcost products                       # card products found, e.g. beta_card:Beta Classic, beta_card:Beta Gold
uv run cardcost wallet --choose                # per bank, pick the cards/account models its documents name
uv run cardcost wallet alpha_card beta_card:Gold   # or name them directly (default: all)
uv run cardcost ask "Einkauf über 200 EUR in der Schweiz"   # flags: --amount --kind cash|purchase --country US --days 30
uv run cardcost ask "300 EUR abheben" --used c24=2 --used revolut_standard=3:150
uv run cardcost matrix --countries DE,FR,US    # which card wins for which amount: "1-375 EUR -> alpha_card; 376-2000 EUR -> beta_card:Gold"
uv run cardcost matrix --used c24=0  # bands for the *next* withdrawal, given allowance usage so far
uv run cardcost review list
uv run cardcost review edited 7 --set min_eur=6,50 --quote "3,0 % mind. 6,50 EUR" --reviewer me   # used on the next question
uv run uvicorn cardcost.api:app               # GET /ask?q=..., POST /webhooks/new-document
```

**Free allowances.** Real price lists waive the cash fee in three ways, each a `FeeSchedule` field:
`free_count` (C24 Smartkonto: "4 x 0,00 EUR", then 2,00 EUR), `free_amount_eur` (Revolut: "5 Abhebungen oder 200 €, je nachdem,
was zuerst eintritt", then 2 %, min 1 €) and `free_from_eur` (Trade Republic: "1 € für Abhebungen unter 100 €").
Whether a withdrawal is free depends on what you already used this period, which no document knows. `ask` therefore asks
for each card with an allowance (count, plus EUR if there is an amount cap), or takes `--used card=N[:EUR[:FX_EUR]]`; the API and MCP
take the same `used` strings. If usage is not given, the allowance counts as used up, so the advisor never claims "free" on a guess.
A withdrawal that only partly fits the amount cap is charged in full, because none of the documents says how an overrun is charged.
FX has its own allowance (`fx_free_eur`, Revolut: "Wechsellimit von 1.000 EUR pro Monat", then 0,5 %). There the document
does say that only the excess is charged, so only the excess is. Account-model prices (HVB: the Mastercard costs 2,50 EUR in
the AktivKonto) are extracted as separate products named `<card> / <Kontomodell>` and picked in the wallet (`wallet --choose`).
If a wallet entry fits two products equally (or none), `ask` lists the candidates and saves your pick; the API returns
`choose_product` and takes `wallet=`, the MCP tools return `choose_one_of`. A question that names one card ("… mit der C24
Mastercard") is answered for that card only; "Welche Karte ist am günstigsten …" compares the whole wallet.

**Webhook**: `X-Timestamp: <unix s>` and `X-Signature: hex(HMAC-SHA256(CARDCOST_WEBHOOK_SECRET, "<timestamp>.<raw body>"))`,
body `{"event_id": "...", "path": "data/private/x.pdf"}`. A request is rejected if it is older than 5 minutes, if its event id was already seen (it gets 200 and is not queued again), or if the path is outside `data/private/`.
The endpoint returns 200 and parses the file in the background; its fees reach the app with the next `cardcost ingest <file>`.

**MCP** (read-only tools `get_fee(card, amount_eur, used)`, `compare_cards(amount_eur, country, used)`):

```bash
claude mcp add cardcost -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY -e CARDCOST_MODEL=claude-sonnet-5-5 \
  -- uv run --directory "$PWD" cardcost-mcp
```

## Eval

`evals/golden.json`: 20 hand-checked questions over the 3 synthetic PDFs in `samples/`. They include 4 "not stated" questions, compound and umlaut terms, amounts on both sides of each minimum-fee crossover (200 / 250 / 750 EUR), and an injection test.
Each question's expected costs are written out in its `_hand` field. `evals/run_eval.py` scores each step separately:
retrieval (expected page in the card's top 3, 17 questions), context (expected page among the passages the extractor actually
receives at ingest: the fixed fee-terms query's top-k, with k growing by one per 3 pages), extraction (exact Decimal match, null must be null),
cost (one-card questions: that card's total, unknown must be unknown) and ranking (only for comparison questions, so a one-card
question never fails on another card's fee). Extraction, cost and ranking are scored from the committed fees files (`samples/fees.json`, written by
`cardcost ingest samples/*.pdf --fees samples/fees.json`, and `catalog/fees.json`), so CI needs no key
and fails if hybrid extraction accuracy is below 0.9.

| mode | retrieval@3 | context | extraction | cost | ranking |
|---|---|---|---|---|---|
| bm25 | 1.00 | 1.00 | _pending live run_ | _pending_ | _pending_ |
| vector | 0.94 | 1.00 | _pending_ | _pending_ | _pending_ |
| hybrid | 0.94 | 1.00 | _pending_ | _pending_ | _pending_ |

`evals/golden_real.json` is a **draft** of 20 questions over the 6 real price lists (C24, DKB, HVB, ING, Revolut,
Trade Republic). They cover the allowance rules on both sides of each limit, Revolut's FX allowance, a "kostenlos" fee, the DKB
counter-vs-ATM trap, HVB's two-column layout and account-model prices. The expected values were drafted from the extracted
text and checked against the calc, but **not yet verified by a human against the PDFs**. Questions marked `VERIFY` rest on an
interpretation. Run it with `--golden evals/golden_real.json`.

The catalog: `catalog/sources.toml` records each price list's id, bank and official URL; the reviewed copy is
`catalog/docs/<id>.pdf`, and the id is the card id everywhere (golden sets, `--used`, LLM cache keys).

| real docs (draft) | retrieval@3 | context | extraction | cost | ranking |
|---|---|---|---|---|---|
| bm25 | 0.90 | 1.00 | _pending live run_ | _pending_ | _pending_ |
| vector | 0.60 | 1.00 | _pending_ | _pending_ | _pending_ |
| hybrid | 0.70 | 1.00 | _pending_ | _pending_ | _pending_ |

How it got here (each step one commit, numbers on the 18-question draft unless noted):

| change | bm25@3 | vector@3 | hybrid@3 |
|---|---|---|---|
| first run | 0.78 | 0.67 | 0.72 |
| drop kerning spaces (ING "Aus lands einsatz entgelt") | 0.83 | 0.61 | 0.72 |
| read two-column pages column by column (HVB) | 0.89 | 0.61 | 0.72 |
| +2 questions (r19 HVB AktivKonto, r20 Revolut FX), 20 total | 0.90 | 0.60 | 0.70 |

The kerning fix *lowered* vector@3 (r11 now lands on ING's girocard page, which uses the same words). Retrieval@3 understates what
extraction gets: the fee-terms query rescues most misses. Context recall was 0.90 for hybrid before k scaled with document size
(+~28 % passages), and is 0.95 after. The last context misses were Revolut's FX section (r13/r20). Revolut calls that fee "Wechselgebühr". The fee-terms query now
holds every name the six price lists use for each fee (one line per fee; Währungsumrechnungsentgelt, Wechselgebühr/Wechsellimit,
Abhebung were missing). Context recall is 1.00 in every mode; synthetic is unchanged.

**Checking the draft:** `uv run python evals/verify_golden.py evals/golden_real.json > evals/golden_real_sheet.md` reads each PDF
with plain pdfplumber (not our ingest). For every expected number it lists the lines on the expected page that contain it, each
with the line before as context. All 20 questions' numbers are found. I read the sheet against the hand notes and found
no contradiction. A human sign-off is still missing, and the `VERIFY` questions (r04, r09, r11, r18, r19) rest on interpretations
that only a person, or the bank, can settle.

Retrieval@1 (synthetic): bm25 0.65, vector 0.65, hybrid 0.71. The remaining hybrid miss is q02 *"Ich hebe 300 EUR … ab"*: a separable
German verb ("hebe … ab" means "abheben", to withdraw), and neither side links it to "Bargeldauszahlung". Extraction does not depend on this question's retrieval,
because the advisor always adds a fixed fee-terms query.

## A failure the eval found

The first retrieval run gave BM25 0.82 @3, and q04 ("Wie hoch ist das **Fremdwährungsentgelt** der Alpha Card?") missed,
although that exact word is on page 2. The cause: BM25 was indexed over all cards, but search is filtered to one
card. "Alpha" and "Card" are rare corpus-wide, so pages repeating the card name outscored the fee term.
**Fix:** one BM25 index per card (IDF within the card's own pages). BM25 went from 0.82 to 1.00 @3. A unit test also caught that
zero-score BM25 passages were entering RRF in arbitrary order. They are now dropped before fusion.

## A second failure: real PDFs

ING's price list came out of ingest as bare values ("kostenlos 2,20 % …") with no row labels, so no reader could tell which fee
a number belonged to. pdfplumber detects the whole page layout as one "table", and `extract()` drops text that is not in a cell.
**Fix:** a detected table is used only if its cells hold at least 80 % of the words in its area. Otherwise the area is read as prose.
The beta sample's real fee table is still rendered as rows (test), and the synthetic retrieval numbers did not change.

## Two more real-PDF failures

ING's PDF places space glyphs *on top of* the next letter, so text came out as "Aus lands einsatz entgelt" and neither BM25 nor the
embeddings matched "Auslandseinsatzentgelt". Raising pdfplumber's `x_tolerance` did not help. **Fix:** drop every space char that
overlaps the next char on its line. HVB prints two text columns, and pdfplumber interleaved them line by line. **Fix:** split at a
central gutter, but only when the right side is not mostly fee values, because C24's and DKB's label/value fee layouts also have a
gutter and must stay whole (tested).

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
- Allowances are tracked per wallet entry. C24's footnote shares one allowance across EUR and FX withdrawals, which fits;
  allowances shared between two cards of the same account do not.
- Account-model products are matched by words: the exact name first, then the product containing every word of the wallet entry
  with the fewest extra words. Two equally good candidates are never guessed between: the user chooses.
- Which card a question names is matched against the file name (`traderepublik` ~ "Trade Republic": fuzzy
  for long names, exact for short ids like `ing`). A bank whose name differs more from its file name needs a name list.
- Product names come from the LLM per extraction; a saved pick stays valid only while the extractor names it the same way
  (exact match first, then words).
- The column split uses thresholds fitted on six price lists (gutter at 45-57 % of the width, right side < 30 % fee values).
  A test pins which pages split (HVB 1-9, 11, 12; Trade Republic 1), so any change to them shows up. Full-width lines that span
  the gutter (headings) are read whole.
- The golden set for the real price lists is a draft that no human has verified yet.

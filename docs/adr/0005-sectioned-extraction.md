# Ingest reads a price list section by section; the whole-document call is gone

Supersedes the single call of [ADR 0004](0004-whole-document-extraction.md), which sent the whole price list to the LLM
at once; keeps its finding that no fee page may be missed.

One call on a whole price list had to find every priced row, read it and copy its numbers and quote in one long answer,
and the long lists lost rows or whole products. Code now cuts the converted text (ADR 0003) into sections by its layout:
the headings, the tables and their header rows. Ingest makes one small call on the document's outline (its headings and
table headers, no prices) that names the cards, the account models, plans and statuses, and which headings are about
card fees; then one call per section under those headings, or under no heading at all. Every number in a section is
tagged, and the model answers with tags, never with numbers; code builds the rules from them, so the quote and page come
from the section itself and a number cannot be misread or invented.

No fee page can be missed silently: every price line lands in a section, a section the outline call rules out is
logged as skipped, and a section answered with no fee is logged, so an offline check finds the sections the model passed
over. A fee that fails to build is retried once and then dropped alone; the rest of the list is kept and the errors go
to the review queue as one item. The outline call carries the token budget check (`MAX_INPUT_TOKENS`): a list over it
is flagged and not sent, never truncated.

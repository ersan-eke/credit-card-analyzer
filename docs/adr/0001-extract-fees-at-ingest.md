# Fees are extracted once per price list, not per question

The tool is a public web page and users pick cards from an operator-maintained catalog instead of uploading documents, so
every price list is known before any question is asked. We extract each price list's fees once when it is added or changes,
review the result, and answer questions from the stored fees with no LLM call. Per-question extraction (the earlier design,
with an LLM cache to avoid paying twice) would make every visitor cost tokens and seconds and let anyone run up the bill.
Retrieval and extraction remain, but as the ingestion pipeline that turns PDFs into reviewed fee data.

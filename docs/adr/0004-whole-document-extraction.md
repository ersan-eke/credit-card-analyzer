# Ingest sends the whole price list to the LLM; retrieval is gone

Supersedes the last sentence of [ADR 0001](0001-extract-fees-at-ingest.md), which kept retrieval as part of ingest.

Retrieval with a generic fee query reached the fee page for only 0.73 of the golden questions, and every page it missed
was a fee the model could not record. A price list is 1k–27k tokens, so the whole converted text (ADR 0003) fits one Haiku
call: ingest makes one call per changed price list and the model sees every page. The fee pages can no longer be missed,
and BM25, the embedding model and PyTorch leave the install and the CI cache.

Rules the model records are checked in code before they are stored: the quote is verbatim on its page of the converted
text, and every number of the rule appears in its quote. A text over the token budget (`MAX_INPUT_TOKENS`, estimated at
three characters per token) is flagged and not sent, never truncated, so a long price list cannot lose its tail unseen.

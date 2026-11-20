# Prompt score history

Predictions per failure class are written here before each run.

| version | golden | schema | temp | tokens in/out | all | dev | holdout | no examples | no example banks | empty lists | missing | extra | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## extract-v8 predictions

Written 2026-11-20 before the run. 91 golden rules (61 dev, 30 holdout). Probe (revolut_standard): content of 2 of 3 rules right, 684 output tokens, no prose or thinking; the scorer counted all 3 missing, so labels and matching cost recall. Haiku runs at the API default temperature (the SDK has no temperature parameter), so the `temp` column below does not apply.

| class | expected missing rules |
|---|---|
| a schema gaps | 12 |
| b labels | 10 |
| c truncation and quotes | 8 (lists that fail whole count all their rules) |
| d wrong content | 6 |

| view | recall | precision |
|---|---|---|
| all | 0.55 | 0.60 |
| holdout | 0.45 | 0.50 |
| extract-v8 | 9be45ba4 | b943e106 | 0 | 414520/20977 | 0.09/0.29 | 0.13/0.30 | 0.00/0.00 | 0.08/0.24 | 0.00/0.00 | 4: bbva c24 tfbank_mastercard_gold traderepublik | 91 | 22 |  |

## extract-v8 analysis

v8 scored recall 0.09 / precision 0.29 against predicted 0.55 / 0.60; holdout 0.00 / 0.00 against 0.45 / 0.50. Nothing truncated (every list stopped with `tool_use`, 293 to 4972 output tokens, 20977 in total), so class c is empty. Counts of misses are 91 missing and 22 extra over all lists. What the prediction missed: the dominant failure is **under-extraction** (class d). Haiku answers with a handful of rules and confidence 0.6-0.7: consorsbank has three products and returns one product with one rule in 379 tokens; hvb returns 2 rules. The second failure (class a) is **fees outside the five events**: bbva and traderepublik return rules with `event: []` (card issuance), the list fails validation twice and counts as returned nothing; tfbank fails a number-not-in-quote check; c24 a quote not found on page 3; the same cause gives extras like `transfer_fee`. Class b (labels) cannot be separated from these until more rules come back. Holdout: all three lists extracted, with 30 golden rules, only counts are looked at. Suspected golden errors: none seen yet.

## extract-v9 change set and predictions

Change set: (1) a required `inventory` array before `products` in the tool schema, one line per priced row, as the place where the "walk the document" step happens; the system prompt asks one rule per inventory line, every row of every product. (2) An explicit scope rule: a fee for none of the five events is not a rule (card issuance, account, transfer, PIN fees), a rule has at least one event. No examples added.

Predicted: lists returning nothing 4 -> 1; missing rules 91 -> 55; extras 22 -> 15; all recall 0.40, precision 0.55; holdout recall 0.35, precision 0.50. Output tokens roughly double (inventory lines).

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

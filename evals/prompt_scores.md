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
| extract-v9 | 9be45ba4 | 50ea5329 | 0 | 353906/35927 | 0.06/0.27 | 0.09/0.29 | 0.00/0.00 | 0.06/0.24 | 0.02/0.20 | 3: c24 hvb ing | 94 | 16 |  |

## extract-v9 analysis

v9: all 0.06 / 0.27, dev 0.09 / 0.29, holdout 0.00 / 0.00 (v8: 0.09 / 0.29, 0.13 / 0.30, 0.00 / 0.00): no gain; predicted 0.40 / 0.55. Lists returning nothing 4 -> 3 (c24, hvb, ing). Gain over v8 is negative, so it does not count towards the stop rule yet (first run after v8). Stop rule (d), holdout lags dev by 0.09, is not read as overfitting: both are at the floor, holdout recall is 0.00 because ing returned nothing.
Dev findings, from the recording and the failure list: (1) **leaked example**: the inventory example in the prompt was real consorsbank text and one list answered `inventory: [that line], products: []` (class d, my error). (2) **Conventions** (class d): rules extracted with the right price but a wrong `when` or event, so they count as one miss plus one extra: foreign-currency fee with `currency ["other"]` only (traderepublik) or `event ["payment"]` only (tfbank); `network ["other"]` invented where the list names no machine (hanseatic_genialcard); `counter_cash` added to a plain cash fee (tfbank); product names given for single-card lists (revolut_standard "Revolut Standard", hanseatic_goldcard "GoldCard", tfbank). (3) **Credit rules missing** on hanseatic_goldcard, genialcard and tfbank (class a/d). (4) c24 fails the number-in-quote check (`2.00` not in the quote) and consorsbank returns one product of three. Suspected golden errors: revolut_ultra and others have no `holding` rule while the model finds a 60 EUR monthly subscription; the golden may deliberately leave plan prices out; report only.

## extract-v10 change set and predictions

Change set: inventory example made abstract and "never empty" added (finding 1); conventions stated in the prompt: foreign-currency fee = both currency values and both events, network only where the text names the machine, counter_cash only for Schalter, single card = null product, interest rate per year is a credit rule (findings 2, 3). No example from holdout banks. Predicted: lists returning nothing 3 -> 1; all recall 0.30, precision 0.45; holdout recall 0.20, precision 0.40.
| extract-v10 | 9be45ba4 | 50ea5329 | 0 | 376474/58128 | 0.16/0.59 | 0.23/0.62 | 0.00/0.00 | 0.11/0.45 | 0.08/0.50 | 3: bbva c24 ing | 84 | 11 |  |

## extract-v10 analysis

v10: all 0.16 / 0.59, dev 0.23 / 0.62, holdout 0.00 / 0.00 (v9: 0.06 / 0.27): gain +0.10 / +0.32; predicted 0.30 / 0.45, so recall below and precision above. Lists returning nothing 3 (bbva, c24, ing). 84 missing, 11 extra. The v10 conventions worked (extras 16 -> 11, hanseatic and traderepublik now match). Remaining dev findings: (1) **products collapse**: in 8 of 20 answers the inventory has 17-60 lines but products holds one rule in total (consorsbank 23 -> 1, revolut_standard 38 -> 1, hvb 22 -> 1); when inventory and rules agree (11 -> 11, 19 -> 19) they score. Class d, the model stops after the first rule. (2) bbva fails on one quote not found (page 4), c24 on a number not in its quote (`0.00`): one bad rule rejects the whole list, class c. (3) Facts for the one plan a list is for (`plan: Standard (Teil I)` on revolut_standard) make a rule differ from the golden's unconditioned one (class b). (4) Golden question: no golden rule has the event holding, so every subscription or card fee the model records (revolut_plus 2.99, revolut_premium 7.99) is an extra; report to the operator whether holding belongs in the golden, no change made. Holdout: ing returns nothing, counts only.

## extract-v11 change set and predictions

Change set: each inventory line ends with `-> <event or skip>` and the prompt asks one rule per non-skip line, with a check before closing products (finding 1); no facts for the one plan a whole list is for (finding 3). Predicted: lists returning nothing 3 -> 2; all recall 0.30, precision 0.55; holdout recall 0.15, precision 0.40.
| extract-v11 | 9be45ba4 | 50ea5329 | 0 | 359653/45523 | 0.17/0.50 | 0.24/0.50 | 0.00/1.00 | 0.12/0.37 | 0.07/0.80 | 2: c24 ing | 83 | 17 |  |

## extract-v11 analysis

v11: all 0.17 / 0.50, dev 0.24 / 0.50, holdout 0.00 / 1.00 (v10: 0.16 / 0.59): gain +0.01 recall, -0.09 precision, below 0.02 on both (first such run; the stop rule needs two in a row); predicted 0.30 / 0.55. Lists returning nothing 3 -> 2 (c24, ing). 83 missing, 17 extra. The inventory tags did not stop the collapse: 11 of 19 answers have 6-30 inventory lines to be written as rules and one to five rules in products (consorsbank 12 -> 1, revolut_standard 30 -> 1, hvb 18 -> 1). Precision fell because more rules arrive with a wrong when or event. Observation: collapsed answers all carry confidence 0.3-0.5 and `confidence` is written before `rules` in the schema, so the model may fix "incomplete" first and then write short. Class d. Holdout: precision 1.00 on a handful of rules, counts only.

## extract-v12 change set and predictions

Change set: schema order only, `rules` before `confidence` (one change, a test of the hypothesis). Predicted: collapsed answers 11 -> 5; all recall 0.28, precision 0.50; holdout recall 0.15; lists returning nothing 2.
| extract-v12 | 9be45ba4 | e227673b | 0 | 347137/42675 | 0.19/0.73 | 0.27/0.76 | 0.00/0.00 | 0.14/0.63 | 0.12/0.78 | 3: c24 revolut_premium revolut_standard | 81 | 7 |  |

## extract-v12 analysis

v12: all 0.19 / 0.73, dev 0.27 / 0.76, holdout 0.00 / 0.00 (v11: 0.17 / 0.50): gain +0.02 recall, +0.23 precision; predicted 0.28 / 0.50, so precision far above, recall just under. Lists returning nothing 3 (c24, revolut_premium, revolut_standard); 81 missing, 7 extra. Moving `confidence` after `rules` removed most wrong rules (extras 17 -> 7) but not the collapse: 9 of 18 answers still hold under a third of their non-skip inventory lines as rules. Class d stays dominant; class c (c24 fails validation on every version, one bad rule rejects the list) is the second.
Holdout vs dev: 0.00 against 0.27 recall, lag over 0.05, **stop rule (d) applies**. The label lists (the only holdout detail read) show a naming cause, class b, not only overfitting: the model names `dkb:Visa Debitkarte 1A` (golden `dkb:Visa Debitkarte`) and `ing:VISA Card [Debitkarte]` (golden `ing:VISA Card`): footnote markers and bracket suffixes copied into the product name; every rule under such a label is missing. Counts of holdout failures: dkb 13 missing, n26 10 missing and 1 extra, ing 7 missing.
Suspected golden errors / open: no `holding` events in the golden (extras if recorded); golden questions for which `ing` and `dkb` labels carry no marker.
Tuning stopped here by rule (d) with 5 of 6 runs used; recorded Ruling in the ledger. The operator may override (a run 6 with a naming rule: no footnote marker or bracket in a product name).
| extract-v12 (model: claude-sonnet-5-5) | 9be45ba4 | e227673b | 0 | 317425/113214 | 0.39/0.47 | 0.47/0.45 | 0.20/0.67 | 0.34/0.39 | 0.22/0.72 | 4: c24 consorsbank dkb hvb | 61 | 44 |  |

## extract-v12 on claude-sonnet-5-5 (model row, not a prompt version)

Same prompt and schema, `tool_choice` dropped (Sonnet 5.5 rejects a forced tool; `LLM._call` retries once without it, so this is not the identical request). All 0.39 / 0.47, dev 0.47 / 0.45, holdout 0.20 / 0.67 against Haiku's 0.19 / 0.73, 0.27 / 0.76, 0.00 / 0.00. Lists returning nothing: c24, consorsbank, dkb, hvb. 61 missing, 44 extra. Output 113k tokens against Haiku's 43k: Sonnet thinks (a `thinking` block precedes the tool call) and 3 answers hit `max_tokens` at 16000 (class c); collapse 3 of 17 answers against 9 of 18.
Haiku misses Sonnet fixes (model limit): 14 dev and 6 holdout rules; Sonnet has no miss Haiku lacks (0). Misses both share (golden, scorer, prompt or validation suspects): 37 dev, 24 holdout. Dev: consorsbank 13, hvb 10, c24 6 (lists that fail validation or truncate on both models), revolut_plus 4, revolut_standard 4 (labels and facts). Precision is lower than Haiku's because Sonnet records more rules with wrong conditions or duplicate prices; the scorer's questions fail with `rules tie` on revolut_standard (two `cash_fee` rules) and tfbank (`interest` and `effective_interest`), a prompt/schema finding. No decision on a separate extraction model: operator's.

## extract-v13 change set and predictions

Run 6 of 6, operator's override of stop rule (d) (2026-11-21). One change: the product name carries no footnote marker and no bracketed suffix. The wording is generic: the holdout labels that showed the problem (read from the label diff only) are not in the prompt. Predicted: holdout recall 0.00 -> 0.15 (dkb and ing rules get a matching label), all recall 0.19 -> 0.26, precision 0.73 -> 0.75; dev unchanged within noise (Haiku at the default temperature). If holdout stays 0.00, naming was not the cause.
| extract-v13 | 9be45ba4 | e227673b | 0 | 359537/36276 | 0.17/0.52 | 0.24/0.55 | 0.00/0.00 | 0.12/0.38 | 0.07/0.67 | 3: c24 consorsbank revolut_standard | 83 | 16 |  |

## extract-v13 analysis

v13 (run 6 of 6): all 0.17 / 0.52, dev 0.24 / 0.55, holdout 0.00 / 0.00 (v12: 0.19 / 0.73, 0.27 / 0.76, 0.00 / 0.00): no gain, predicted 0.26 / 0.75 and holdout 0.15. Lists returning nothing 3 (c24, consorsbank, revolut_standard). The naming rule worked for one label: `dkb:Visa Debitkarte 1A` is gone from the label diff and `dkb:Visa Debitkarte` is no longer missing, yet dkb recall stays 0.00, so the dkb rules mismatch on content (class d, counts only). `ing:VISA Card [Debitkarte]` still carries the bracket: Haiku did not follow the rule. So naming alone was not the holdout cause. The precision drop from 0.73 to 0.52 is the size of the run-to-run spread plus the changes of the day (v11 0.50, v12 0.73, v13 0.52 on prompts that differ by one sentence): Haiku at the default temperature is noisy at about +-0.1 on precision. The noise rerun was not done.
Stop: 6 of 6 runs used. Best Haiku version by precision remains v12; best by recall v12 (0.19). No prompt reaches 0.9 / 0.9; the remaining failures are structural (collapse, one rule rejecting a list, ing and dkb content), see the report.

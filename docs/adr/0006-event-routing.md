# Code routes each section view to the event questions it needs; the model triages what no keyword explains

Amends [ADR 0005](0005-sectioned-extraction.md): the outline call no longer decides which sections are read, and
`section_skipped` is gone.

One prompt for every card fee made the model mix events: a cash fee read as a payment fee, a foreign-currency fee
as a cash fee. Each view now gets one short prompt and tool per route (`cash`, `payment`, `credit`, `holding`), each
asking one event question. Code picks the routes by keyword, matched on NFC-casefolded headings and lines (`bargeldlos`
is not a cash word). A view under a "Beispiel" heading is an example and gets no call. A price line is detected on the
original text, because a casefolded "eur" would not match the price pattern. A view with a price line no keyword
explains is triaged: one small model call that names the routes the view states a card fee for, then one call per
route it names. So code routes and the model triages.

This reverses the v14 anti-goal that code never decides what the model reads. Keywords are a shortcut, not a gate: they
save a call when the words are clear, but a price line they do not explain still reaches the model, so a fee is not
lost for lack of a keyword. On the dev golden rules every rule is routed by keyword (`TRIAGE_ONLY` is empty).

Known limit: a keyword for the wrong event. A view that names an ATM in a payment fee gets the cash route as well; the
route prompt then finds no cash fee and logs `section_no_fee`, or reads a fee under the wrong event. Triage does not
catch this, since the view is already routed.

Logs per view: `section_example`, `section_routed`, `section_triaged`, `section_triage_failed` (the call failed; the error is queued), `section_no_route` (triage named none);
`section_repeat`, `section_no_fee` and `section_invalid` stay. `evals/section_stats.py` estimates the calls and input
tokens offline, counting triage as a cash-sized call per flagged view.

# Golden rules review (#20)

Per card: open the PDF at the given page, tick each rule when quote, price, event, `when` and allowance match the price list. Items marked **DECIDE** carry a `review` note: pick a reading, then edit `evals/golden_real.json` (delete the `review` field once resolved).

91 rules, **36 to decide**, 5 quotes not found verbatim.


## traderepublik  (`catalog/docs/traderepublik.pdf`)

- [x] `tr.atm.small` Abhebung unter 100 EUR — events atm; price {"flat_eur": "1"}; when {"amount": {"max": "100"}}
  - p.1: «Kosten bei Einsatz der Debitkarte | 1 € für Abhebungen unter 100 €»
  - **DECIDE**: Withdrawals from 100 EUR are free by implication only; the list states no 0. correct.
- [x] `tr.fx` Währungsumrechnungsentgelt — events payment,atm; price {"flat_eur": "0"}; when {"currency": ["EEA_non_EUR", "other"]}
  - p.1: «Währungsumrechnungsentgelt | 0 €»

## hanseatic_genialcard  (`catalog/docs/hanseatic_genialcard.pdf`)

- [x] `gc.atm.home` Bargeldabhebung Inland — events atm; price {"flat_eur": "3.95"}; when {"region": ["home"]}
  - p.1: «Bargeldabhebungen am Geldautomaten innerhalb Deutschlands 1 | 3,95 € pro Auftrag» correct, possible atm fees which is defined by separate user input
- [x] `gc.atm.abroad` Bargeldabhebung Ausland — events atm; price {"flat_eur": "0"}; when {"region": ["EEA", "outside_EEA"]}
  - p.1: «Bargeldabhebungen am Geldautomaten außerhalb Deutschlands 1 | 0 €» it says outside germany, region EEA means not germany right?, also possible atm fees which is defined by separate user input
- [x] `gc.fx` Entgelt für den Auslandseinsatz — events payment,atm; price {"flat_eur": "0"}; when {"currency": ["EEA_non_EUR", "other"]}
  - p.1: «Entgelt für den Auslandseinsatz weltweit 2 | 0 €»
- [x] `gc.gambling` Casino, Lotterie, Wetten — events payment; price {"percent": "3", "min_eur": "3.95"}; when {"merchant": ["gambling"]}
  - p.1: «Transaktionsentgelt für Zahlungen an Casinobetriebe, Lotteriegesellschaften und Wettbüros (MCC 7995 / 9406) 3 | 3 % des Betrags, mind. 3,95 €»
- [x] `gc.financial` Wertpapierhandel, Finanzinstitute, Geldtransfer, Krypto — events payment; price {"percent": "3", "min_eur": "3.95"}; when {"merchant": ["financial"]}
  - p.1: «den Einsatz bei Finanzinstituten (MCC 6012), für die Ausführung eines Geldtransfers (MCC 4829) und den Kauf von Kryptowährungen (MCC 6051) 3 | 3 % des Betrags, mind. 3,95 €»
  - **DECIDE**: The list names no merchant class for these MCCs; 'financial' is my name for it. financial is good, we can add an explanation for it in the app like trading/investment/transfer/institutes
- [x] `gc.credit` Sollzinssatz — events credit; price {"percent": "18.30"}
  - p.1: «Sollzinssatz | 18,30 %»
  - **DECIDE**: The list states the rate for instalment use only; whether purchases are interest-free is not stated. it should be only instalment

## hanseatic_goldcard  (`catalog/docs/hanseatic_goldcard.pdf`)

- [x] `gold.atm` Bargeldabhebung — events atm; price {"flat_eur": "0"}
  - p.1: «Bargeldabhebungen am Geldautomaten 1 | 0 €»
- [x] `gold.fx` Entgelt für den Auslandseinsatz — events payment,atm; price {"flat_eur": "0"}; when {"currency": ["EEA_non_EUR", "other"]}
  - p.1: «Entgelt für den Auslandseinsatz weltweit 2 | 0 €»
- [x] `gold.gambling` Casino, Lotterie, Wetten — events payment; price {"percent": "3", "min_eur": "3.95"}; when {"merchant": ["gambling"]}
  - p.1: «Transaktionsentgelt für Zahlungen an Casinobetriebe, Lotteriegesellschaften und Wettbüros (MCC 7995 / 9406) 3 | 3 % des Betrags, mind. 3,95 €»
- [x] `gold.financial` Wertpapierhandel, Finanzinstitute, Geldtransfer, Krypto — events payment; price {"percent": "3", "min_eur": "3.95"}; when {"merchant": ["financial"]}
  - p.1: «den Einsatz bei Finanzinstituten (MCC 6012), für die Ausführung eines Geldtransfers (MCC 4829) und den Kauf von Kryptowährungen (MCC 6051) 3 | 3 % des Betrags, mind. 3,95 €»
  - **DECIDE**: The list names no merchant class for these MCCs; 'financial' is my name for it. answered in hanseatic_genial
- [x] `gold.credit` Sollzinssatz — events credit; price {"percent": "16.30"}
  - p.1: «Sollzinssatz | 16,30 %»
  - **DECIDE**: The list states the rate for instalment use only; whether purchases are interest-free is not stated. answered in hanseatic_genial

## tfbank_mastercard_gold  (`catalog/docs/tfbank_mastercard_gold.pdf`)

- [x] `tf.atm` Bargeldabhebung weltweit — events atm; price {"flat_eur": "0"}
  - p.1: «Bargeldabhebungen weltweit (Manche ausgebenden Stellen erheben eigene Gebühren, welche wir nicht beeinflussen können und nicht erstatten) | 0,- €»
- [x] `tf.fx` Auslandseinsatzgebühr — events payment,atm; price {"flat_eur": "0"}; when {"currency": ["EEA_non_EUR", "other"]}
  - p.1: «Zahlungen in Fremdwährungen werden nach dem Referenzwechselkurs der Kartenorganisation Mastercard in Euro umgerechnet. | 0,- €»
- [x] `tf.credit` Sollzins — events credit; price {"percent": "22.60"}
  - p.1: «22,60 % (veränderlich*)»
  - **DECIDE**: Purchases carry no interest when the statement is paid in full by the due date; cash and transfers are excluded. The rule format cannot say that yet (#25). : so basically 0 with a hint? 

## bbva:Debitkarte  (`catalog/docs/bbva.pdf`)

- [x] `bbvad.pay` Zahlung mit Debitkarte — events payment; price {"flat_eur": "0"}
  - p.3: «Bargeldlose Zahlungen mit Debitkarte weltweit in allen Währungen der Welt | Kostenlos Umrechnung in realen Wechselkurs ohne Fremdwährungszuschlag». it has limits thought right? page 1 says: Debitkarte: Betragsgrenzen für die Nutzung eines Zahlungsinstruments: 2000Euro/Tag, 12000Euro/Monat, Tageslimit für Einkäufe mit der Debitkarte: Maximal 3000Euro/Tag (standardmäßig 2000Euro/Tag). or is that something else? could be important for the user
- [x] `bbvad.atm.big` Abhebung ab 150 EUR — events atm; price {"flat_eur": "0"}; when {"currency": ["EUR"], "amount": {"min": "150"}}
  - p.3: «Kostenlos, wenn die Abhebung mindestens 150 € oder mehr beträgt, ansonsten 2 €.»
  - **DECIDE**: Basiskonto holders pay nothing at any amount; not drafted (account model). add Basiskonto account as an option then
- [x] `bbvad.atm.small` Abhebung unter 150 EUR — events atm; price {"flat_eur": "2"}; when {"currency": ["EUR"], "amount": {"max": "150"}}
  - p.3: «Kostenlos, wenn die Abhebung mindestens 150 € oder mehr beträgt, ansonsten 2 €.»
- [x] `bbvad.atm.fx` Abhebung in Fremdwährung — events atm; price {"flat_eur": "2"}; when {"currency": ["EEA_non_EUR", "other"]}
  - p.3: «Geldautomaten in Fremdwährung (außer | 2 € pro Abhebung.» correct, again basiskonto is free. it says "außer Basiskonto"
- [x] `bbvad.atm.es` Abhebung an BBVA-Automaten in Spanien — events atm; price {"flat_eur": "0"}; when {"country": ["ES"], "network": ["own"]}
  - p.4: «Bargeldabhebungen mit der Debitkarte an BBVA-Geldautomaten in Spanien | Kostenlos»
  - **DECIDE**: The operator fee at BBVA's own Spanish machines is not stated. no operator fee for their own atms.

## bbva:Kreditkarte  (`catalog/docs/bbva.pdf`)

- [x] `bbvac.atm` Bargeldauszahlung — events atm; price {"percent": "4", "min_eur": "3"}
  - p.2: «Bargeldauszahlung (In- und Ausland) | 4,00 % (mind. 3,00 €)»
- [x] `bbvac.fx` Währungsumrechnungsentgelt — events payment,atm; price {"percent": "0"}; when {"currency": ["EEA_non_EUR", "other"]}
  - p.2: «Währungsumrechnungsentgelt | 0,00 %»

## c24  (`catalog/docs/c24.pdf`)

- [x] `c24.atm.eur.smart` Bargeldauszahlung eur Smartkonto — events atm; price {"flat_eur": "2"}; when {"currency": ["EUR"], "facts": {"account_model": ["C24 Smartkonto"]}}; allowance {"count": 4, "period": "calendar_month"}
  - p.3: «Mit der C24 Mastercard (kostenlos) | 4 x 0,00 EUR 7 | 20 x 0,00 EUR 7 | 20 x 0,00 EUR 7 | - | | Jede weitere Bargeldauszahlung mit der C24 Mastercard | 2,00 EUR | 2,00 EUR | 2,00 EUR | 2,00 EUR |»
  - **DECIDE**: The 4 / 20 free withdrawals are shared between EUR and foreign-currency ATMs (footnote 7). The list states no foreign-currency fee for card payments, so none is drafted.  correct. and we are talking about mastercard, not girocard
- [x] `c24.atm.eur.plusmax` Bargeldauszahlung eur Pluskonto/Maxkonto — events atm; price {"flat_eur": "2"}; when {"currency": ["EUR"], "facts": {"account_model": ["C24 Pluskonto", "C24 Maxkonto"]}}; allowance {"count": 20, "period": "calendar_month"}
  - p.3: «Mit der C24 Mastercard (kostenlos) | 4 x 0,00 EUR 7 | 20 x 0,00 EUR 7 | 20 x 0,00 EUR 7 | - | | Jede weitere Bargeldauszahlung mit der C24 Mastercard | 2,00 EUR | 2,00 EUR | 2,00 EUR | 2,00 EUR |»
  - **DECIDE**: The 4 / 20 free withdrawals are shared between EUR and foreign-currency ATMs (footnote 7). yes, answered
- [x] `c24.atm.eur.basis` Bargeldauszahlung eur Basiskonto — events atm; price {"flat_eur": "2"}; when {"currency": ["EUR"], "facts": {"account_model": ["C24 Basiskonto"]}}
  - p.3: «Jede weitere Bargeldauszahlung mit der C24 Mastercard | 2,00 EUR | 2,00 EUR | 2,00 EUR | 2,00 EUR |»
- [x] `c24.atm.fx.smart` Bargeldauszahlung fx Smartkonto — events atm; price {"flat_eur": "2"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"account_model": ["C24 Smartkonto"]}}; allowance {"count": 4, "period": "calendar_month"}
  - p.3: «Mit der C24 Mastercard (kostenlos) | 4 x 0,00 EUR 7 | 20 x 0,00 EUR 7 | 20 x 0,00 EUR 7 | - | | Jede weitere Bargeldauszahlung mit der C24 Mastercard | 2,00 EUR | 2,00 EUR | 2,00 EUR | 2,00 EUR |»
  - **DECIDE**: The 4 / 20 free withdrawals are shared between EUR and foreign-currency ATMs (footnote 7). yes, answered
- [x] `c24.atm.fx.plusmax` Bargeldauszahlung fx Pluskonto/Maxkonto — events atm; price {"flat_eur": "2"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"account_model": ["C24 Pluskonto", "C24 Maxkonto"]}}; allowance {"count": 20, "period": "calendar_month"}
  - p.3: «Mit der C24 Mastercard (kostenlos) | 4 x 0,00 EUR 7 | 20 x 0,00 EUR 7 | 20 x 0,00 EUR 7 | - | | Jede weitere Bargeldauszahlung mit der C24 Mastercard | 2,00 EUR | 2,00 EUR | 2,00 EUR | 2,00 EUR |»
  - **DECIDE**: The 4 / 20 free withdrawals are shared between EUR and foreign-currency ATMs (footnote 7). yes, answered
- [x] `c24.atm.fx.basis` Bargeldauszahlung fx Basiskonto — events atm; price {"flat_eur": "2"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"account_model": ["C24 Basiskonto"]}}
  - p.3: «Jede weitere Bargeldauszahlung mit der C24 Mastercard | 2,00 EUR | 2,00 EUR | 2,00 EUR | 2,00 EUR |»

## consorsbank:Visa Card Debit  (`catalog/docs/consorsbank.pdf`)

- [x] `cvd.atm.small` Bargeldauszahlung EWR in Euro unter 50 — events atm; price {"flat_eur": "1.95"}; when {"currency": ["EUR"], "amount": {"max": "50"}}
  - p.8: «Beträge unter 50,00 Euro - 1,95 Euro 2 Beträge ab einschl. 50,00 Euro - kostenlos 2»
  - **DECIDE**: Columns of the Girokonto price table are unnamed in the extracted text (first two equal, third '-'); drafted from the first. girokonto unlimited is like an account model (third colunmn) and '-' means no cost. second column is for girokonto für Eröffnungen bis 26.03.2021 which is also an account model option. default is the first one, the other ones are choices for the user. here it is <50 = 1.95 and 50>= is free
- [x] `cvd.atm.big` Bargeldauszahlung EWR in Euro ab 50 — events atm; price {"flat_eur": "0"}; when {"currency": ["EUR"], "amount": {"min": "50"}}
  - p.8: «Beträge unter 50,00 Euro - 1,95 Euro 2 Beträge ab einschl. 50,00 Euro - kostenlos 2»
  - **DECIDE**: Columns of the Girokonto price table are unnamed in the extracted text (first two equal, third '-'); drafted from the first.
- [x] `cvd.atm.eea` Bargeldauszahlung EWR in anderer Währung — events atm; price {"percent": "2.10"}; when {"currency": ["EEA_non_EUR"]}
  - p.8: «im EWR auf den jeweiligen, nicht auf Euro lautenden Auszahlungsbetrag | 2,10 % 2»
- [x] `cvd.atm.out` Bargeldauszahlung außerhalb des EWR — events atm; price {"percent": "2.10"}; when {"region": ["outside_EEA"]}
  - p.8: «außerhalb des EWR auf den jeweiligen Auszahlungsbetrag | 2,10 % 2»
- [x] `cvd.pay.eur` Karteneinsatz in Euro — events payment; price {"flat_eur": "0"}; when {"currency": ["EUR"]}
  - p.8: «Karteneinsatz im Europäischen Wirtschaftsraum (EWR) in Euro | kostenlos 2»
- [x] `cvd.pay.fx` Karteneinsatz in Fremdwährung — events payment; price {"percent": "2.10"}; when {"currency": ["EEA_non_EUR", "other"]}
  - p.8: «Karteneinsatz im EWR auf den jeweiligen, nicht auf Euro lautenden Umsatz | 2,10 % 2»
  - **DECIDE**: The list gives one price inside and one outside the EWR; merged because both are 2,10 %. yes, in this case
- [x] `cvd.gambling` Wettbüros, Casinos, Lotterien — events payment; price {"percent": "2.50", "min_eur": "5"}; when {"merchant": ["gambling"]}
  - p.8: «Karteneinsatz in Wettbüros, Casinobetrieben und Lotteriegesell- schaften | 2,50 %, mind. 5,00 Euro 8»

## consorsbank:Credit Card Gold Light  (`catalog/docs/consorsbank.pdf`)

- [x] `ccgl.atm` Bargeldauszahlung — events atm; price {"flat_eur": "0"}
  - p.8: «Bargeldauszahlung an allen Visa-zugänglichen Geldausgabe automaten | kostenlos 2 | kostenlos 2 | -»
  - **DECIDE**: Columns of the Girokonto price table are unnamed in the extracted text (first two equal, third '-'); drafted from the first. yes, as answered for debit card
- [x] `ccgl.pay` Karteneinsatz — events payment; price {"flat_eur": "0"}
  - p.8: «Karteneinsatz außerhalb des EWR auf den jeweiligen Umsatz | kostenlos 2 | kostenlos 2 | -»
  - **DECIDE**: Free in euro, in other EWR currencies and outside the EWR (three lines), merged. yes, in this case
- [x] `ccgl.gambling` Wettbüros, Casinos, Lotterien — events payment; price {"percent": "2.50", "min_eur": "5"}; when {"merchant": ["gambling"]}
  - p.8: «Karteneinsatz in Wettbüros, Casinobetrieben und Lotterie gesellschaften | 2,50 %, mind. 5,00 Euro | 2,50 %, mind. 5,00 Euro | -»

## consorsbank:Visa Card Gold  (`catalog/docs/consorsbank.pdf`)

- [x] `cvg.atm` Bargeldauszahlung — events atm; price {"flat_eur": "0"}
  - p.8: «Bargeldauszahlung an allen Visa-zugänglichen Geldausgabe automaten | kostenlos 2 | kostenlos 2 | kostenlos 2»
  - **DECIDE**: Columns of the Girokonto price table are unnamed in the extracted text (first two equal, third '-'); drafted from the first. yes, answered in debit card
- [x] `cvg.pay` Karteneinsatz — events payment; price {"flat_eur": "0"}
  - p.8: «Karteneinsatz im Europäischen Wirtschaftsraum (EWR) in Euro | kostenlos 2 | kostenlos 2 | kostenlos 2»
  - **DECIDE**: Free in every currency (four lines), merged.
- [x] `cvg.gambling` Wettbüros, Casinos, Lotterien — events payment; price {"percent": "2.50", "min_eur": "5"}; when {"merchant": ["gambling"]}
  - p.8: «Karteneinsatz in Wettbüros, Casinobetrieben und Lotterie gesellschaften | 2,50 %, mind. 5,00 Euro | 2,50 %, mind. 5,00 Euro | 2,50 %, mind. 5,00 Euro»

## n26  (`catalog/docs/n26.pdf`)

- [x] `n26.atm.standard` Abhebung in Euro N26 Standard — events atm; price {"flat_eur": "2"}; when {"currency": ["EUR"], "facts": {"plan": ["N26 Standard"]}}; allowance {"count": 2, "period": "calendar_month"}
  - p.3: «- Für N26 Standard und N26 Business Standard Kontoinhaber | 2 Abhebungen kostenlos pro Kalendermonat, 2,00 € für jede weitere Abhebung»
  - **DECIDE**: The list calls this 'Fair Use Policy'; it does not apply to customers with an Austrian delivery address. yes, so default is the rule, but if original austrian delivery address then free
- [x] `n26.atm.smart` Abhebung in Euro N26 Smart — events atm; price {"flat_eur": "2"}; when {"currency": ["EUR"], "facts": {"plan": ["N26 Smart"]}}; allowance {"count": 3, "period": "calendar_month"}
  - p.3: «- Für N26 Smart, N26 Business Smart Kunden | 3 Abhebungen kostenlos pro Kalendermonat, 2,00 € für jede weitere Abhebung»
  - **DECIDE**: The list calls this 'Fair Use Policy'; it does not apply to customers with an Austrian delivery address.
- [x] `n26.atm.go` Abhebung in Euro N26 Go — events atm; price {"flat_eur": "2"}; when {"currency": ["EUR"], "facts": {"plan": ["N26 Go"]}}; allowance {"count": 5, "period": "calendar_month"}
  - p.3: «- N26 Go und N26 Business Go Kunden | 5 Abhebungen kostenlos pro Kalendermonat, 2,00 € für jede weitere Abhebung»
  - **DECIDE**: The list calls this 'Fair Use Policy'; it does not apply to customers with an Austrian delivery address.
- [x] `n26.atm.metal` Abhebung in Euro N26 Metal — events atm; price {"flat_eur": "2"}; when {"currency": ["EUR"], "facts": {"plan": ["N26 Metal"]}}; allowance {"count": 8, "period": "calendar_month"}
  - p.3: «- Für N26 Metal und N26 Business Metal Kunden | 8 Abhebungen kostenlos pro Kalendermonat, 2,00 € für jede weitere Abhebung»
  - **DECIDE**: The list calls this 'Fair Use Policy'; it does not apply to customers with an Austrian delivery address.
- [x] `n26.atm.fx.free` Abhebung in sonstigen Währungen Go/Metal — events atm; price {"flat_eur": "0"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"plan": ["N26 Go", "N26 Metal"]}}
  - p.3: «Für N26 Go, N26 Metal, N26 Business Go und N26 Business Metal Kunden | Kostenlos»
- [x] `n26.atm.fx` Abhebung in sonstigen Währungen Standard/Smart — events atm; price {"percent": "1.7"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"plan": ["N26 Standard", "N26 Smart"]}}
  - p.3: «| 1,7% des Umsatzes»
  - **DECIDE**: Row has no plan label in the extracted text; read as the rest after the Go/Metal row. Whether the free withdrawals also apply in foreign currency is not stated. bad layout by the price list. the row would be: Für Business- und Girokonto sowie N26 Smart, N26 Business
Smart (Gilt nicht für Flex- und Basiskonto Kunden) - 1,7% des Umsatzes
- [x] `n26.pay` Zahlung weltweit — events payment; price {"flat_eur": "0"}
  - p.3: «Bargeldlose Zahlungen mit Mastercard & Maestro Karte weltweit und in allen Währungen | Kostenlos Umrechnung zum echten Devisenmittelkurs ohne Fremdwährungszuschlag»
- [x] `n26.atm.flex.eur` Abhebung in Euro Flex/Basiskonto — events atm; price {"flat_eur": "2"}; when {"currency": ["EUR"], "facts": {"plan": ["N26 Flex", "N26 Basiskonto"]}}
  - p.7: «2,00 € pro Geldabhebung am Automaten»
- [x] `n26.atm.flex.fx` Abhebung in sonstigen Währungen Flex/Basiskonto — events atm; price {"flat_eur": "2"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"plan": ["N26 Flex", "N26 Basiskonto"]}}
  - p.7: «2,00 € pro Geldabhebung am Geldautomaten zzgl. 1,7% vom Umsatz»
  - **DECIDE**: Flat 2,00 and 1,7 % are one fee; drafted as two rules (flat + stacked percent). yes, so 1.7% on the Umsatz and 2 Euro flat. or if it is at an CASh26 partner then only the 2 euro flat
- [x] `n26.atm.flex.fxpct` Auslandsanteil Flex/Basiskonto — events atm; price {"percent": "1.7"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"plan": ["N26 Flex", "N26 Basiskonto"]}}; stacks
  - p.7: «2,00 € pro Geldabhebung am Geldautomaten zzgl. 1,7% vom Umsatz». what is Auslandsanteil. you already covered this case in the question before

## ing:VISA  (`catalog/docs/ing.pdf`)

- [x] `ing.atm.home` Bargeldauszahlung Deutschland — events atm; price {"flat_eur": "0"}; when {"region": ["home"]}
  - p.2: «an allen Geldautomaten mit VISA Zeichen in Deutschland Mindestabhebebetrag 50 €. Liegt der auf dem Konto verfügbare Betrag darunter, können auch niedrigere Beträge abgehoben werden: | kostenlos» important: if you have more than 50, you need to withdraw more than 50
- [x] `ing.atm.euro` Bargeldauszahlung Eurowährung — events atm; price {"flat_eur": "0"}; when {"currency": ["EUR"], "region": ["EEA"]}
  - p.2: «in Ländern mit Eurowährung Mindestabhebebetrag 50 €. Liegt der auf dem Konto verfügbare Betrag darunter, können auch niedrigere Beträge abgehoben werden: | kostenlos, ggf. zuzüglich Entgelt des Geldautomatenbetreibers»
  - ⚠ quote not found verbatim in the converted text; check the PDF. it is there. row looks like this right below the an allen Geldautomaten mit VISA Zeichen in Deutschland: n Ländern mit Eurowährung \n Mindestabhebebetrag 50 €. Liegt der auf dem Konto verfügbare Betrag darunter, können auch niedrigere
Beträge abgehoben werden: - kostenlos, ggf. zuzüglich Entgelt
des ­Geld­auto­maten­betreibers
- [x] `ing.atm.eea` Bargeldauszahlung EWR-Fremdwährung — events atm; price {"percent": "2.20"}; when {"currency": ["EEA_non_EUR"]}
  - p.2: «in Ländern des EWR 2 mit anderer EWR-Währung: | Auf den Betrag in Euro 2,20 % Auslandseinsatzentgelt»
  - ⚠ quote not found verbatim in the converted text; check the PDF. it is there. it says EWR^2 though (small thing)
- [x] `ing.atm.other` Bargeldauszahlung andere Länder — events atm; price {"percent": "2.20"}; when {"currency": ["other"]}
  - p.2: «in allen anderen Ländern mit Fremdwährung 4 : | Auf den Betrag in Euro 2,20 % Auslandseinsatzentgelt»
  - ⚠ quote not found verbatim in the converted text; check the PDF. its there with Fremdwährung^4
- [x] `ing.pay.euro` Bezahlen Eurowährung — events payment; price {"flat_eur": "0"}; when {"currency": ["EUR"]}
  - p.2: «in Ländern mit Eurowährung: | kostenlos |»
- [x] `ing.pay.eea` Bezahlen EWR-Fremdwährung — events payment; price {"percent": "2.20"}; when {"currency": ["EEA_non_EUR"]}
  - p.2: «in Ländern des EWR 2 mit anderer EWR-Währung: | auf den Betrag in Euro 2,20 % Auslandseinsatzentgelt»
  - ⚠ quote not found verbatim in the converted text; check the PDF. its there with EWR^2
- [x] `ing.pay.other` Bezahlen andere Länder — events payment; price {"percent": "2.20"}; when {"currency": ["other"]}
  - p.3: «in allen anderen Ländern mit Fremdwährung 4 : Ausgabe nur in Verbindung mit einem Zahlungskonto | auf den Betrag in Euro 2,20 % Auslandseinsatzentgelt»
  - ⚠ quote not found verbatim in the converted text; check the PDF. its there with Fremdwährung^4

## dkb:Visa Debitkarte  (`catalog/docs/dkb.pdf`)

- [x] `dkbd.pay.fx.std` Kartenzahlung in Fremdwährung Standardleistung — events payment; price {"percent": "2.20"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"status": ["Standardleistung"]}}
  - p.1: «außerhalb des EWR 1G in jeder Fremdwährung 1K | 2,20 % vom Zahlungsbetrag 1J | kostenlos» merged EWR and not EWR
- [x] `dkbd.pay.fx.akt` Kartenzahlung in Fremdwährung Aktivstatus — events payment; price {"flat_eur": "0"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"status": ["Aktivstatus"]}}
  - p.1: «außerhalb des EWR 1G in jeder Fremdwährung 1K | 2,20 % vom Zahlungsbetrag 1J | kostenlos» again merged in/non EWR
- [x] `dkbd.gamb.std` Spiele mit Geldeinsatz Standardleistung — events payment; price {"percent": "3"}; when {"merchant": ["gambling"], "facts": {"status": ["Standardleistung"]}}; stacks
  - p.1: «Bei Lotterien, Casinos, Wett- und sonstigen Anbietern von Spielen mit Geldeinsatz | zzgl. 3,00 % vom Zahlungsbetrag 1L | 3,00 % vom Umsatz 1L»
- [x] `dkbd.gamb.akt` Spiele mit Geldeinsatz Aktivstatus — events payment; price {"percent": "3"}; when {"merchant": ["gambling"], "facts": {"status": ["Aktivstatus"]}}
  - p.1: «Bei Lotterien, Casinos, Wett- und sonstigen Anbietern von Spielen mit Geldeinsatz | zzgl. 3,00 % vom Zahlungsbetrag 1L | 3,00 % vom Umsatz 1L»
- [x] `dkbd.atm.eur` Geldautomat in Euro — events atm; price {"flat_eur": "0"}; when {"currency": ["EUR"]}
  - p.1: «An Geldautomaten in Euro innerhalb des EWR 1G in EWR-Währung 1H (außer Euro) 1I | kostenlos seitens der DKB AG 1N 2,20 % vom Umsatz seitens DKB AG 1J 1N | kostenlos seitens der DKB AG 1N kostenlos seitens der DKB AG 1N»
  - **DECIDE**: The row for euro and for other EWR currencies is merged in the extracted text; euro read as free for both statuses. yes, merged
- [x] `dkbd.atm.fx.std` Geldautomat in Fremdwährung Standardleistung — events atm; price {"percent": "2.20"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"status": ["Standardleistung"]}}
  - p.1: «außerhalb des EWR 1G in jeder Fremdwährung 1K | 2,20 % vom Umsatz seitens DKB AG 1J 1N | kostenlos seitens der DKB AG 1N» merged
- [x] `dkbd.atm.fx.akt` Geldautomat in Fremdwährung Aktivstatus — events atm; price {"flat_eur": "0"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"status": ["Aktivstatus"]}}
  - p.1: «außerhalb des EWR 1G in jeder Fremdwährung 1K | 2,20 % vom Umsatz seitens DKB AG 1J 1N | kostenlos seitens der DKB AG 1N» merged
- [x] `dkbd.cnt` Auszahlung am Schalter — events counter_cash; price {"percent": "3", "min_eur": "5"}
  - p.2: «| in Euro | 3,00 % vom verfügten Betrag, mind. 5,00 EUR 2A | 3,00 % vom verfügten Betrag, mind. 5,00 EUR 2A |» in Euro is important
- [x] `dkbd.cnt.fx.std` Schalter in Fremdwährung Standardleistung — events counter_cash; price {"percent": "2.20"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"status": ["Standardleistung"]}}; stacks
  - p.2: «außerhalb des EWR 2B in jeder Fremdwährung 2F | 3,00 % vom verfügten Betrag, mind. 5,00 EUR zzgl. 2,20 % vom verfügten Betrag 2A 2E | 3,00 % vom verfügten Betrag, mind. 5,00 EUR 2A». so  5,5 percent right? 3 percent + 2.20 percent vom verfügten Betrag

## dkb:Visa Kreditkarte  (`catalog/docs/dkb.pdf`)

- [x] `dkbk.pay` Kartenzahlung — events payment; price {"flat_eur": "0"}
  - p.2: «innerhalb des EWR 2B in Nicht-EWR-Währung 2C, 2F | kostenlos |»
  - **DECIDE**: Free in euro, EWR currencies and elsewhere (four lines), merged. yes merged
- [x] `dkbk.gamb` Spiele mit Geldeinsatz — events payment; price {"percent": "3"}; when {"merchant": ["gambling"]}
  - p.2: «bei Lotterien, Casinos, Wett- und sonstigen Anbietern von Spielen mit Geldeinsatz | 3,00% vom Umsatz 2A»
- [x] `dkbk.atm` Geldautomat — events atm; price {"flat_eur": "0"}
  - p.2: «außerhalb des EWR 2B in jeder Fremdwährung 2F | kostenlos seitens der DKB AG 2N»
- [x] `dkbk.cnt` Auszahlung am Schalter — events counter_cash; price {"percent": "3", "min_eur": "5"}
  - p.2: «| in Euro | 3,00 % vom verfügten Betrag, mind. 5,00 EUR 2A |»

## hvb:HVB Mastercard  (`catalog/docs/hvb.pdf`)

- [x] `hvb.atm.own` Geldautomat der HypoVereinsbank in EUR — events atm; price {"flat_eur": "0"}; when {"currency": ["EUR"], "network": ["own"]}
  - p.5: «– Bargeldauszahlung mit der Kreditkarte am Geldautomaten innerhalb
der EU/EWR-Staaten in EUR
– an Geldautomaten der HypoVereinsbank kostenfrei
– an allen anderen Geldautomaten 2% mind. 5 EUR» 
- [x] `hvb.atm.other` Geldautomat anderer Banken in EUR — events atm; price {"percent": "2", "min_eur": "5"}; when {"currency": ["EUR"], "network": ["other"]}
  - p.5: «– Bargeldauszahlung mit der Kreditkarte am Geldautomaten innerhalb
der EU/EWR-Staaten in EUR
– an Geldautomaten der HypoVereinsbank kostenfrei
– an allen anderen Geldautomaten 2% mind. 5 EUR»
  - **DECIDE**: Account models outside the three named are priced as the 'all other' default; the list also has other cards with other prices (not drafted). there are two Ausnahme: Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold im HVB ExklusivKonto, Depot Global, HVB Platinumkonto (Hauptkonto) = kostenlos. Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold im HVB AktivKonto und HVB PlusKonto = 2,50 Euro. so yes this is default
- [x] `hvb.atm.other.ex` Geldautomat anderer Banken in EUR (Exklusiv/Depot Global/Platinum) — events atm; price {"flat_eur": "0"}; when {"currency": ["EUR"], "network": ["other"], "facts": {"account_model": ["HVB ExklusivKonto", "HVB Depot Global Konto", "HVB PlatinumKonto"]}}
  - p.5: «– Bargeldauszahlung mit der Kreditkarte am Geldautomaten innerhalb
der EU/EWR-Staaten in EUR
– an Geldautomaten der HypoVereinsbank kostenfrei
– an allen anderen Geldautomaten 2% mind. 5 EUR
Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold
im HVB ExklusivKonto, Depot Global, HVB Platinumkonto
(Hauptkonto) kostenfrei»
- [x] `hvb.atm.other.ap` Geldautomat anderer Banken in EUR (Aktiv/Plus) — events atm; price {"flat_eur": "2.50"}; when {"currency": ["EUR"], "network": ["other"], "facts": {"account_model": ["HVB AktivKonto", "HVB PlusKonto"]}}
  - p.5: «– an allen anderen Geldautomaten 2% mind. 5 EUR
Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold
im HVB ExklusivKonto, Depot Global, HVB Platinumkonto
(Hauptkonto) kostenfrei
Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold
im HVB AktivKonto und HVB PlusKonto 2,50 EUR»
- [x] `hvb.atm.fx` Geldautomat in Fremdwährung — events atm; price {"percent": "2", "min_eur": "5"}; when {"currency": ["EEA_non_EUR", "other"]}
  - p.5: «– Bargeldauszahlung mit der Kreditkarte an fremden
Geldautomaten in Fremdwährung (Umrechnungskurs
siehe Teil B, letztes Unterkapitel) 2% mind. 5 EUR»
- [x] `hvb.atm.fx.ex` Geldautomat in Fremdwährung (Exklusiv/Depot Global/Platinum) — events atm; price {"flat_eur": "0"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"account_model": ["HVB ExklusivKonto", "HVB Depot Global Konto", "HVB PlatinumKonto"]}}
  - p.5: «– Bargeldauszahlung mit der Kreditkarte an fremden
Geldautomaten in Fremdwährung (Umrechnungskurs
siehe Teil B, letztes Unterkapitel) 2% mind. 5 EUR
Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold
im HVB ExklusivKonto, Depot Global, HVB Platinumkonto
(Hauptkonto) kostenfrei»
- [x] `hvb.atm.fx.ap` Geldautomat in Fremdwährung (Aktiv/Plus) — events atm; price {"flat_eur": "2.50"}; when {"currency": ["EEA_non_EUR", "other"], "facts": {"account_model": ["HVB AktivKonto", "HVB PlusKonto"]}}
  - p.5: «siehe Teil B, letztes Unterkapitel) 2% mind. 5 EUR
Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold
im HVB ExklusivKonto, Depot Global, HVB Platinumkonto
(Hauptkonto) kostenfrei
Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold
im HVB AktivKonto und HVB PlusKonto 2,50 EUR»
- [x] `hvb.cnt` Auszahlung am Schalter fremder Kreditinstitute — events counter_cash; price {"percent": "3", "min_eur": "5"}
  - p.5: «– Bargeldauszahlung am Schalter fremder Kreditinstitute
mit einer von der Bank ausgegebenen Kreditkarte in EUR
und in Fremdwährung 3% mind. 5 EUR»
  - **DECIDE**: Stated for 'a credit card issued by the bank', not for the Mastercard by name.
- [x] `hvb.pay.eur` Einsatz zum Bezahlen in EUR — events payment; price {"flat_eur": "0"}; when {"currency": ["EUR"]}
  - p.8: «– Einsatz der Kreditkarte zum Bezahlen in EUR kostenfrei»
- [x] `hvb.pay.fx` Einsatz zum Bezahlen in Fremdwährung — events payment; price {"percent": "1.75"}; when {"currency": ["EEA_non_EUR", "other"]}
  - p.8: «– Einsatz der Kreditkarte zum Bezahlen in Fremdwährung
(Umrechnungskurs siehe Teil B, letztes Unterkapitel) 1,75% vom Umsatz»

## revolut_standard  (`catalog/docs/revolut_standard.pdf`)

- [x] `revs.atm` Bargeldabhebung nach Freikontingent — events atm; price {"percent": "2", "min_eur": "1"}; allowance {"count": 5, "amount_eur": "200", "period": "rolling_month"}
  - p.3: «Bis zu 5 Abhebungen am Geldautomaten oder 200 € (je nachdem, was zuerst eintritt) pro rollierendem Monat sind gebührenfrei. Weitere Abhebungen werden mit 2 % des Abhebungsbetrags oder 1 € berechnet, je nachdem, welcher Betrag höher ist.»
- [x] `revs.fx` Faire Nutzungsgebühr Währungswechsel — events payment,atm; price {"percent": "0.5"}; when {"currency": ["EEA_non_EUR", "other"]}; allowance {"amount_eur": "1000", "period": "calendar_month"}; stacks
  - p.5: «Standard:Wechsellimit von 1.000 EUR pro Monat. Für jeden zusätzlichen Währungswechsel fällt eine faire Nutzungsgebühr von 0,5 % an.»
  - **DECIDE**: Calendar or rolling month for the exchange limit is not stated ('pro Monat'); drafted as calendar month. it is rolling month
- [x] `revs.weekend` Wochenendgebühr Währungswechsel — events payment,atm; price {"percent": "1"}; when {"currency": ["EEA_non_EUR", "other"], "weekend": true}; stacks
  - p.5: «Wenn du am Wochenende (zwischen 17 Uhr New Yorker Zeit am Freitag und 18 Uhr New Yorker Zeit am Sonntag) wechselst, fällt eine Gebühr von 1 % an.»
  - **DECIDE**: Whether the weekend fee replaces the 0,5 % beyond the limit or adds to it is not stated; 'currency already held' fact not drafted. it is on page 6 already. it adds up with the 0.5%

## revolut_plus  (`catalog/docs/revolut_plus.pdf`)

- [x] `revp.atm` Bargeldabhebung nach Freikontingent — events atm; price {"percent": "2", "min_eur": "1"}; allowance {"amount_eur": "200", "period": "rolling_month"}
  - p.12: «Kostenlose Bargeldabhebungen bis zu 200 € pro rollierendem Monat, danach fällt eine Gebühr an. Diese Gebühr beträgt 2 % des abgehobenen Betrags bei einer Mindestgebühr von 1 € pro Abhebung.» also watch out for Bargeldauszahlungen an Geldautomaten mit BLIK
- [x] `revp.fx` Faire Nutzungsgebühr Währungswechsel — events payment,atm; price {"percent": "0.5"}; when {"currency": ["EEA_non_EUR", "other"]}; allowance {"amount_eur": "3000", "period": "calendar_month"}; stacks
  - p.6: «Plus: Wechsellimit von 3.000 EUR pro Monat. Für jeden zusätzlichen Währungswechsel fällt eine faire Nutzungsgebühr von 0,5 % an.»
  - **DECIDE**: Calendar or rolling month for the exchange limit is not stated ('pro Monat'); drafted as calendar month. The same list says elsewhere 'Standard und Plus: Wechsellimit von 1.000 EUR pro Monat' (p.14); the two contradict. rolling month. on first page it says Teil 1 (page 6) is for: Wenn du in Deutschland wohnst und ein Konto mit einer IBAN beginnend mit DE
erhalten hast, bist du Kunde der Revolut Bank UAB, Zweigniederlassung Deutschland. Teil 2 is for Revolut Bank UAB: Wenn du ein Kunde der Revolut Bank UAB bist, scrolle bitte nach unten zu Teil II, um
die für dich relevanten Bedingungen zu sehen. 
- [x] `revp.weekend` Wochenendgebühr Währungswechsel — events payment,atm; price {"percent": "0.5"}; when {"currency": ["EEA_non_EUR", "other"], "weekend": true}; stacks
  - p.6: «Wenn du am Wochenende (zwischen 17 Uhr New Yorker Zeit am Freitag und 18 Uhr New Yorker Zeit am Sonntag) wechselst, fällt eine Gebühr von 0,5 % an.»
  - **DECIDE**: Whether the weekend fee replaces the 0,5 % beyond the limit or adds to it is not stated; 'currency already held' fact not drafted. adds up

## revolut_premium  (`catalog/docs/revolut_premium.pdf`)

- [x] `revpr.atm` Bargeldabhebung nach Freikontingent — events atm; price {"percent": "2", "min_eur": "1"}; allowance {"amount_eur": "400", "period": "rolling_month"}
  - p.12: «Kostenlose Bargeldabhebungen bis zu 400 € pro rollierendem Monat, danach fällt eine Gebühr an. Diese Gebühr beträgt 2 % des abgehobenen Betrags bei einer Mindestgebühr von 1 € pro Abhebung.»
  - **DECIDE**: Premium, Metal and Ultra: 'Kein Wechsellimit. Keine faire Nutzungsgebühr.' states no number, so no rule is drafted and the foreign-currency cost stays unknown. correct, again watch out for Teil 1 and 2 and for BLIK atms

## revolut_metal  (`catalog/docs/revolut_metal.pdf`)

- [x] `revm.atm` Bargeldabhebung nach Freikontingent — events atm; price {"percent": "2", "min_eur": "1"}; allowance {"amount_eur": "800", "period": "rolling_month"}
  - p.13: «Kostenlose Bargeldabhebungen bis zu 800 € pro rollierendem Monat, danach fällt eine Gebühr an. Diese Gebühr beträgt 2 % des abgehobenen Betrags bei einer Mindestgebühr von 1 € pro Abhebung.»
  - **DECIDE**: Premium, Metal and Ultra: 'Kein Wechsellimit. Keine faire Nutzungsgebühr.' states no number, so no rule is drafted and the foreign-currency cost stays unknown. same caveats as above

## revolut_ultra  (`catalog/docs/revolut_ultra.pdf`)

- [x] `revu.atm` Bargeldabhebung nach Freikontingent — events atm; price {"percent": "2", "min_eur": "1"}; allowance {"amount_eur": "2000", "period": "rolling_month"}
  - p.13: «Kostenlose Bargeldabhebungen bis zu 2.000€ pro rollierendem Monat, danach fällt eine Gebühr an. Diese Gebühr beträgt 2 % des abgehobenen Betrags bei einer Mindestgebühr von 1€ pro Abhebung.»
  - **DECIDE**: Premium, Metal and Ultra: 'Kein Wechsellimit. Keine faire Nutzungsgebühr.' states no number, so no rule is drafted and the foreign-currency cost stays unknown. same caveats as above

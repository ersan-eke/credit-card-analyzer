# Verification sheet

DRAFT, not yet verified by a human. Drafted from the extracted page text of catalog/docs/*.pdf. Check every expected value against the PDF and remove VERIFY markers before trusting the score. Cash at ATMs only; ATM-operator fees without a stated amount are not added; unknown free-allowance usage counts as used up.

## r01: Was kostet eine Bargeldabhebung von 300 EUR mit der C24 Mastercard, wenn ich diesen Monat schon 2 Mal abgehoben habe?

`c24:Smartkonto`, page 3. Hand: c24 2<4 free 0.00; dkb 0; hvb max(6,5)=6.00; ing 0; rev usage unknown -> assumed used, max(6,1)=6.00; tr >=100 0

Expected cost 0 EUR: correct

- `min_eur` = 2.00: 
  - `Jede weitere Bargeldauszahlung mit der ⏎ 2,00 EUR 2,00 EUR 2,00 EUR 2,00 EUR`
  - `Jede weitere Bargeldauszahlung im ⏎ 2,00 EUR 2,00 EUR 2,00 EUR 2,00 EUR`
  - `Mit der C24 girocard Der Automatenbetreiber erhebt ein direktes Entgelt für jede Bargeldauszahlung5 ⏎ 2. Bargeldauszahlungen am`
  - `Jede weitere Bargeldauszahlung mit der ⏎ 2,00 EUR 2,00 EUR 2,00 EUR 2,00 EUR`
- `free_count` = 4: 
  - `über die ReiseBank AG8 ⏎ 4. Bargeldauszahlungslimite der C24`
  - `Kalendermonat) ⏎ Mit der C24 Mastercard (kostenlos) 4 x 0,00 EUR7 20 x 0,00 EUR7 20 x 0,00 EUR7 -`
  - `Kalendermonat) ⏎ Mit der C24 Mastercard (kostenlos) 4 x 0,00 EUR7 20 x 0,00 EUR7 20 x 0,00 EUR7 -`

## r02: Ich habe mit der C24 Mastercard diesen Monat schon 4 Mal Geld abgehoben. Was kostet die nächste Abhebung von 300 EUR?

`c24:Smartkonto`, page 3. Hand: c24 allowance used 2.00; hvb 6.00; rev 6.00

Expected cost 2.00 EUR: correct

- `min_eur` = 2.00: 
  - `Jede weitere Bargeldauszahlung mit der ⏎ 2,00 EUR 2,00 EUR 2,00 EUR 2,00 EUR`
  - `Jede weitere Bargeldauszahlung im ⏎ 2,00 EUR 2,00 EUR 2,00 EUR 2,00 EUR`
  - `Mit der C24 girocard Der Automatenbetreiber erhebt ein direktes Entgelt für jede Bargeldauszahlung5 ⏎ 2. Bargeldauszahlungen am`
  - `Jede weitere Bargeldauszahlung mit der ⏎ 2,00 EUR 2,00 EUR 2,00 EUR 2,00 EUR`
- `free_count` = 4: 
  - `über die ReiseBank AG8 ⏎ 4. Bargeldauszahlungslimite der C24`
  - `Kalendermonat) ⏎ Mit der C24 Mastercard (kostenlos) 4 x 0,00 EUR7 20 x 0,00 EUR7 20 x 0,00 EUR7 -`
  - `Kalendermonat) ⏎ Mit der C24 Mastercard (kostenlos) 4 x 0,00 EUR7 20 x 0,00 EUR7 20 x 0,00 EUR7 -`

## r03: Ich habe mit Revolut diesen Monat 2 Mal insgesamt 150 EUR abgehoben. Was kostet eine weitere Abhebung von 40 EUR?

`revolut_standard`, page 3. Hand: rev 150+40<=200 and 2<5 free; tr 40<100 1.00; c24 assumed used 2.00; hvb max(0.80,5)=5.00. p12 states it again

Expected cost 0 EUR: correct

- `percent` = 2: 
  - `eintritt) pro rollierendem Monat sind gebührenfrei. Weitere Abhebungen werden ⏎ mit 2 % des Abhebungsbetrags oder 1 € berechnet, je nachdem, welcher Betrag`
  - `Kartenlose Geldautomatenauszahlungen mit BLIK: Für jede Auszahlung berechnen ⏎ wir eine Gebühr von 2 % des abgehobenen Betrags bzw. mindestens 5 PLN (je`
- `min_eur` = 1: 
  - `eintritt) pro rollierendem Monat sind gebührenfrei. Weitere Abhebungen werden ⏎ mit 2 % des Abhebungsbetrags oder 1 € berechnet, je nachdem, welcher Betrag`
- `free_count` = 5: 
  - `Bargeldabhebungen am Geldautomaten ⏎ Bis zu 5 Abhebungen am Geldautomaten oder 200 € (je nachdem, was zuerst`
  - `Kartenlose Geldautomatenauszahlungen mit BLIK: Für jede Auszahlung berechnen ⏎ wir eine Gebühr von 2 % des abgehobenen Betrags bzw. mindestens 5 PLN (je`
- `free_amount_eur` = 200: 
  - `Bargeldabhebungen am Geldautomaten ⏎ Bis zu 5 Abhebungen am Geldautomaten oder 200 € (je nachdem, was zuerst`

## r04 (VERIFY): Revolut: 2 Abhebungen mit zusammen 150 EUR schon gemacht. Was kostet es, jetzt 100 EUR abzuheben?

`revolut_standard`, page 3. Hand: VERIFY: 250>200 -> charged in full max(2,1)=2.00 (doc does not say whether only the 50 EUR overrun is charged); tr 0; c24 2.00; hvb 5.00

Expected cost 2.00 EUR: incorrect, shouldnt be charged in full, first until the limit of 200 is still free, everything after that is charged

- `percent` = 2: 
  - `eintritt) pro rollierendem Monat sind gebührenfrei. Weitere Abhebungen werden ⏎ mit 2 % des Abhebungsbetrags oder 1 € berechnet, je nachdem, welcher Betrag`
  - `Kartenlose Geldautomatenauszahlungen mit BLIK: Für jede Auszahlung berechnen ⏎ wir eine Gebühr von 2 % des abgehobenen Betrags bzw. mindestens 5 PLN (je`
- `min_eur` = 1: 
  - `eintritt) pro rollierendem Monat sind gebührenfrei. Weitere Abhebungen werden ⏎ mit 2 % des Abhebungsbetrags oder 1 € berechnet, je nachdem, welcher Betrag`
- `free_count` = 5: 
  - `Bargeldabhebungen am Geldautomaten ⏎ Bis zu 5 Abhebungen am Geldautomaten oder 200 € (je nachdem, was zuerst`
  - `Kartenlose Geldautomatenauszahlungen mit BLIK: Für jede Auszahlung berechnen ⏎ wir eine Gebühr von 2 % des abgehobenen Betrags bzw. mindestens 5 PLN (je`
- `free_amount_eur` = 200: 
  - `Bargeldabhebungen am Geldautomaten ⏎ Bis zu 5 Abhebungen am Geldautomaten oder 200 € (je nachdem, was zuerst`

## r05: Ich habe mit Revolut diesen Monat schon 5 Mal 50 EUR abgehoben. Was kosten 20 EUR am Automaten?

`revolut_standard`, page 3. Hand: count cap hit first: max(0.40,1)=1.00; tr 20<100 1.00 (tie, label order); c24 2.00; hvb 5.00

Expected cost 1.00 EUR: correct

- `percent` = 2: 
  - `eintritt) pro rollierendem Monat sind gebührenfrei. Weitere Abhebungen werden ⏎ mit 2 % des Abhebungsbetrags oder 1 € berechnet, je nachdem, welcher Betrag`
  - `Kartenlose Geldautomatenauszahlungen mit BLIK: Für jede Auszahlung berechnen ⏎ wir eine Gebühr von 2 % des abgehobenen Betrags bzw. mindestens 5 PLN (je`
- `min_eur` = 1: 
  - `eintritt) pro rollierendem Monat sind gebührenfrei. Weitere Abhebungen werden ⏎ mit 2 % des Abhebungsbetrags oder 1 € berechnet, je nachdem, welcher Betrag`
- `free_count` = 5: 
  - `Bargeldabhebungen am Geldautomaten ⏎ Bis zu 5 Abhebungen am Geldautomaten oder 200 € (je nachdem, was zuerst`
  - `Kartenlose Geldautomatenauszahlungen mit BLIK: Für jede Auszahlung berechnen ⏎ wir eine Gebühr von 2 % des abgehobenen Betrags bzw. mindestens 5 PLN (je`
- `free_amount_eur` = 200: 
  - `Bargeldabhebungen am Geldautomaten ⏎ Bis zu 5 Abhebungen am Geldautomaten oder 200 € (je nachdem, was zuerst`

## r06: Was kostet es, mit der Trade Republic Karte 50 EUR abzuheben?

`traderepublik`, page 1. Hand: '1 € für Abhebungen unter 100 €' -> 1.00; rev assumed used max(1,1)=1.00; c24 2.00; hvb 5.00

Expected cost 1.00 EUR: correct

- `min_eur` = 1: 
  - `Anlagevolumen pro Ausführung: 10 € bis 10.000 €. Konto ⏎ Abwicklungskostenpauschale2 1,00 € Kontoführung kostenfrei`
  - `Ersatzdebitkarte4 Applikation ⏎ je Standardweisung 1,00 € Versand der Debitkarte kostenfrei`
  - `je Standardweisung 1,00 € Versand der Debitkarte kostenfrei ⏎ je spezifische Kundenweisung per 5,00 € Kosten bei Einsatz der Debitkarte 1 € für`
  - `Optionsscheinen oder Zertifikaten ⏎ Handel mit Bezugsrechten jeder Art2 1,00 €`
- `free_from_eur` = 100: 
  - `EMail Abhebungen ⏎ unter 100 €`

## r07: Kostet eine Abhebung von 100 EUR mit Trade Republic etwas?

`traderepublik`, page 1. Hand: exactly 100 is not 'unter 100' -> 0.00; rev 2.00; c24 2.00; hvb 5.00

Expected cost 0 EUR: correct

- `min_eur` = 1: 
  - `Anlagevolumen pro Ausführung: 10 € bis 10.000 €. Konto ⏎ Abwicklungskostenpauschale2 1,00 € Kontoführung kostenfrei`
  - `Ersatzdebitkarte4 Applikation ⏎ je Standardweisung 1,00 € Versand der Debitkarte kostenfrei`
  - `je Standardweisung 1,00 € Versand der Debitkarte kostenfrei ⏎ je spezifische Kundenweisung per 5,00 € Kosten bei Einsatz der Debitkarte 1 € für`
  - `Optionsscheinen oder Zertifikaten ⏎ Handel mit Bezugsrechten jeder Art2 1,00 €`
- `free_from_eur` = 100: 
  - `EMail Abhebungen ⏎ unter 100 €`

## r08: Kostet Geld abheben am Automaten mit der DKB Visa Kreditkarte etwas?

`dkb:Kreditkarte`, page 2. Hand: 'An Geldautomaten in Euro kostenlos seitens der DKB AG'; trap: 'Am Schalter 3,00 %, mind. 5,00 EUR' is the counter, not the ATM; rev 4.00; hvb max(4,5)=5.00

Expected cost 0.00 EUR: correctf

- `percent` = 0: 
  - `An Geldautomaten ⏎ in Euro kostenlos seitens der DKB AG2N`
  - `Kartenversand per Kurier 48,50 EUR ⏎ Notfallbargeld (einmalige weltweite Zusendung von Bargeld) kostenlos`
  - `Notfallbargeld (einmalige weltweite Zusendung von Bargeld) kostenlos ⏎ Notfallkarte (einmalige Ausgabe) kostenlos`
  - `Kreditkartenabrechnung ⏎ in das elektronische Postfach kostenlos`
  - `Kartenzahlung ⏎ in Euro kostenlos`
  - `in Euro kostenlos ⏎ innerhalb des EWR2B in EWR-Währung2C (außer Euro)2D kostenlos`

## r09 (VERIFY): Welche Gebühr nimmt die HVB Mastercard für eine Abhebung von 500 EUR an fremden Geldautomaten?

`hvb:HVB Mastercard`, page 5. Hand: VERIFY: '– an allen anderen Geldautomaten 2% mind. 5 EUR' (two-column page, lines interleave); account exceptions (ExklusivKonto free, AktivKonto 2,50 EUR) ignored; hvb 10.00, rev 10.00 tie -> label order

Expected cost 10.00 EUR: correct but depends on Konto, so that should be verified by the user 

- `percent` = 2: 
  - `den Zahlungsdienste oder sonstigen Dienstleistungen (z. B. Überweisung) bereits in Geldautomaten in Fremdwährung (Umrechnungskurs ⏎ dem Preis für die Kontoführung enthalten sind, der für ein Kontomodell berechnet wird siehe Teil B, letztes Unterkapitel) 2% mind. 5 EUR`
  - `und in Fremdwährung 3% mind. 5 EUR ⏎ 2 Bargeldauszahlung mit der Debitkarte am Geldautomaten Bargeldeinzahlung`
  - `– an Geldautomaten der HypoVereinsbank kostenfrei ⏎ – an Geldautomaten aller Banken der UniCredit Group 2 Bargeldeinzahlung mit der Debitkarte am`
  - `– Bargeldauszahlung mit der Debitkarte am Geldautomaten ⏎ innerhalb der EU/EWR-Staaten in EUR 2 Ausführungsfristen`
  - `– an Geldautomaten der HypoVereinsbank kostenfrei ⏎ – an allen anderen Geldautomaten 2% mind. 5 EUR`
- `min_eur` = 5: 
  - `den Zahlungsdienste oder sonstigen Dienstleistungen (z. B. Überweisung) bereits in Geldautomaten in Fremdwährung (Umrechnungskurs ⏎ dem Preis für die Kontoführung enthalten sind, der für ein Kontomodell berechnet wird siehe Teil B, letztes Unterkapitel) 2% mind. 5 EUR`
  - `– an Geldautomaten der HypoVereinsbank kostenfrei ⏎ – an allen anderen Geldautomaten 2% mind. 5 EUR`
  - `mit einer von der Bank ausgegebenen Kreditkarte in EUR ⏎ und in Fremdwährung 3% mind. 5 EUR`
  - `Ggf. anfallenden Fremdgebühren werden erstattet. ⏎ Seite 5`

## r10: Was kostet die HVB Mastercard für 200 EUR am Geldautomaten einer anderen Bank?

`hvb:HVB Mastercard`, page 5. Hand: hvb max(4,5)=5.00 (minimum side of the 250 EUR crossover); rev 4.00

Expected cost 5.00 EUR: correct but also depends on the Konto

- `percent` = 2: 
  - `den Zahlungsdienste oder sonstigen Dienstleistungen (z. B. Überweisung) bereits in Geldautomaten in Fremdwährung (Umrechnungskurs ⏎ dem Preis für die Kontoführung enthalten sind, der für ein Kontomodell berechnet wird siehe Teil B, letztes Unterkapitel) 2% mind. 5 EUR`
  - `und in Fremdwährung 3% mind. 5 EUR ⏎ 2 Bargeldauszahlung mit der Debitkarte am Geldautomaten Bargeldeinzahlung`
  - `– an Geldautomaten der HypoVereinsbank kostenfrei ⏎ – an Geldautomaten aller Banken der UniCredit Group 2 Bargeldeinzahlung mit der Debitkarte am`
  - `– Bargeldauszahlung mit der Debitkarte am Geldautomaten ⏎ innerhalb der EU/EWR-Staaten in EUR 2 Ausführungsfristen`
  - `– an Geldautomaten der HypoVereinsbank kostenfrei ⏎ – an allen anderen Geldautomaten 2% mind. 5 EUR`
- `min_eur` = 5: 
  - `den Zahlungsdienste oder sonstigen Dienstleistungen (z. B. Überweisung) bereits in Geldautomaten in Fremdwährung (Umrechnungskurs ⏎ dem Preis für die Kontoführung enthalten sind, der für ein Kontomodell berechnet wird siehe Teil B, letztes Unterkapitel) 2% mind. 5 EUR`
  - `– an Geldautomaten der HypoVereinsbank kostenfrei ⏎ – an allen anderen Geldautomaten 2% mind. 5 EUR`
  - `mit einer von der Bank ausgegebenen Kreditkarte in EUR ⏎ und in Fremdwährung 3% mind. 5 EUR`
  - `Ggf. anfallenden Fremdgebühren werden erstattet. ⏎ Seite 5`

## r11 (VERIFY): Ich hebe 300 EUR in den USA ab. Was kostet das mit der ING VISA Card?

`ing:VISA`, page 2. Hand: VERIFY: ing 0 + 2.20% = 6.60; hvb 6.00 + 1.75% purchase FX 5.25 = 11.25 (calc adds FX to cash; doc lists 1,75% for 'Bezahlen' only); c24 2.00 + 0; rev cash fee + 0.5% FX (limit assumed used up)

Expected cost 6.60 EUR: correct, just 2,20% percent

- `percent` = 0: 
  - `in Ländern mit Eurowährung ⏎ Mindestabhebebetrag 50 €. Liegt der auf dem Konto verfügbare Betrag darunter, können auch niedrigere kostenlos, ggf. zuzüglich Entgelt`
  - `in Deutschland: kostenlos ⏎ in Ländern mit Eurowährung: kostenlos`
- `fx_percent` = 2.20: 
  - `Beträge abgehoben werden: des Geld auto maten betreibers ⏎ in Ländern des EWR2 mit anderer EWR-Währung: A uf den Betrag in Euro 2,20 %`
  - `des Geldauto maten betreibers. ⏎ in allen anderen Ländern mit Fremdwährung4: A uf den Betrag in Euro 2,20 %`
  - `in Ländern mit Eurowährung: kostenlos ⏎ in Ländern des EWR2 mit anderer EWR-Währung: a uf den Betrag in Euro 2,20 %`

## r12: Kostet Geld abheben in Frankreich mit der ING VISA Card etwas?

`ing:VISA`, page 2. Hand: eurozone: no FX; 'ggf. zuzüglich Entgelt des Geldautomatenbetreibers' has no amount -> not added; hvb 6.00, rev 6.00

Expected cost 0.00 EUR: correct

- `percent` = 0: 
  - `in Ländern mit Eurowährung ⏎ Mindestabhebebetrag 50 €. Liegt der auf dem Konto verfügbare Betrag darunter, können auch niedrigere kostenlos, ggf. zuzüglich Entgelt`
  - `in Deutschland: kostenlos ⏎ in Ländern mit Eurowährung: kostenlos`

## r13: Was kostet Revolut beim Bezahlen in US-Dollar?

`revolut_standard`, page 5. Hand: 'Standard: Wechsellimit von 1.000 EUR pro Monat ... faire Nutzungsgebühr von 0,5 %', charged on the excess only; usage not given -> limit counted as used up: 0.5% of 100 = 0.50; hvb 1.75; ing 2.20

Expected cost 0.50 EUR: incorrect, the first 1000 euro are free exchange, after that 0,5%, also look out for weekends where additional 1% is being charged (page 6)

- `fx_percent` = 0.5: 
  - `Standard:Wechsellimit von 1.000 EUR pro Monat. Für jeden zusätzlichen ⏎ Währungswechsel fällt eine faire Nutzungsgebühr von 0,5 % an.`
  - `Plus: Wechsellimit von 3.000 EUR pro Monat. Für jeden zusätzlichen ⏎ Währungswechsel fällt eine faire Nutzungsgebühr von 0,5 % an.`
- `fx_free_eur` = 1000: 
  - `zusätzlichen Betrag eine faire Nutzungsgebühr berechnet. Diese Limits sind: ⏎ Standard:Wechsellimit von 1.000 EUR pro Monat. Für jeden zusätzlichen`

## r14: Wie hoch ist das Auslandseinsatzentgelt der ING VISA Card?

`ing:VISA`, page 2. Hand: compound word split by PDF kerning: 'Aus lands einsatz entgelt'; hvb 3.50; ing 4.40; rev 0.5% FX (limit assumed used up)

Expected cost 4.40 EUR: wrong, it is 2,2% so it depends on the amount being withdrawn

- `fx_percent` = 2.20: 
  - `Beträge abgehoben werden: des Geld auto maten betreibers ⏎ in Ländern des EWR2 mit anderer EWR-Währung: A uf den Betrag in Euro 2,20 %`
  - `des Geldauto maten betreibers. ⏎ in allen anderen Ländern mit Fremdwährung4: A uf den Betrag in Euro 2,20 %`
  - `in Ländern mit Eurowährung: kostenlos ⏎ in Ländern des EWR2 mit anderer EWR-Währung: a uf den Betrag in Euro 2,20 %`

## r15: Was kostet die HVB Mastercard beim Bezahlen in Fremdwährung?

`hvb:HVB Mastercard`, page 8. Hand: 'Einsatz der Kreditkarte zum Bezahlen in Fremdwährung ... 1,75% vom Umsatz' (HVB Mastercard block); rev 0.5% FX (limit assumed used up)

Expected cost 1.75 EUR: correct but there is also a mastercard firmenkunden which costs 1% so that should be cleared by the user

- `fx_percent` = 1.75: 
  - `– Einsatz der Kreditkarte zum Bezahlen in Fremdwährung 1 Inlands-Scheckverkehr ⏎ (Umrechnungskurs siehe Teil B, letztes Unterkapitel) 1,75% vom Umsatz – Scheckeinlösungen/Scheckgutschriften (gilt nur für Nichtverbraucher) 0,41 EUR`
  - `– Einsatz der Kreditkarte zum Bezahlen in Fremdwährung über 100,00 EUR bis 12.500,00 EUR oder Gegenwert 20,00 EUR ⏎ – HVB Visa Card 1,75% vom Umsatz über 12.500,00 EUR oder Gegenwert 2,00 ‰, max. 250,00 EUR`

## r16: Gibt es bei Trade Republic ein Währungsumrechnungsentgelt?

`traderepublik`, page 1. Hand: 'Währungsumrechnungsentgelt | 0 €' (a EUR amount, read as 0 %); rev 0.5% FX (limit assumed used up)

Expected cost 0.00 EUR: correct

- `fx_percent` = 0: 
  - `unter 100 € ⏎ je freiwillige Weisung für Wandlung / 10,00 € Währungsumrechnungsentgelt 0 €`
  - `Kapitalmaßnahmen Debitkarte ⏎ Teilnahme Kapitalmaßnahme2 kostenfrei Ausgabe einer virtuellen Debitkarte kostenfrei`
  - `Ersatzdebitkarte4 Applikation ⏎ je Standardweisung 1,00 € Versand der Debitkarte kostenfrei`

## r17: Wie viele kostenlose Abhebungen pro Monat habe ich mit dem C24 Smartkonto?

`c24:Smartkonto`, page 3. Hand: Smartkonto 4 x 0,00 EUR (Plus/Max 20, Basis none); rev assumed used 2.00; hvb 5.00

Expected cost 0 EUR: the answer is 4, expected cost depends on the user

- `free_count` = 4: 
  - `über die ReiseBank AG8 ⏎ 4. Bargeldauszahlungslimite der C24`
  - `Kalendermonat) ⏎ Mit der C24 Mastercard (kostenlos) 4 x 0,00 EUR7 20 x 0,00 EUR7 20 x 0,00 EUR7 -`
  - `Kalendermonat) ⏎ Mit der C24 Mastercard (kostenlos) 4 x 0,00 EUR7 20 x 0,00 EUR7 20 x 0,00 EUR7 -`

## r18 (VERIFY): Ich will in Thailand 1.000 EUR abheben. Welche Karte ist am günstigsten?

`dkb:Kreditkarte`, page 2. Hand: VERIFY: dkb 0; tr 0; c24 2.00 + FX 0 ('In Fremdwährung 0,00 EUR', card payments row); ing 22.00; hvb 20.00 + 17.50 = 37.50; rev cash fee + 0.5% FX (limit assumed used up)

Expected ranking dkb:Kreditkarte > traderepublik > c24:Smartkonto > ing:VISA > revolut_standard > hvb:HVB Mastercard: first it depends on which cards / konto types the user has. then for example for dkb if he has aktivstatus or how many withdrawals he already had. shouldnt c24 be 0 because it has 4 free withdrawals? revolut could be 200 free after that 
2%. hvb has 2% or free (see exceptions)
- `percent` = 0: 
  - `An Geldautomaten ⏎ in Euro kostenlos seitens der DKB AG2N`
  - `Kartenversand per Kurier 48,50 EUR ⏎ Notfallbargeld (einmalige weltweite Zusendung von Bargeld) kostenlos`
  - `Notfallbargeld (einmalige weltweite Zusendung von Bargeld) kostenlos ⏎ Notfallkarte (einmalige Ausgabe) kostenlos`
  - `Kreditkartenabrechnung ⏎ in das elektronische Postfach kostenlos`
  - `Kartenzahlung ⏎ in Euro kostenlos`
  - `in Euro kostenlos ⏎ innerhalb des EWR2B in EWR-Währung2C (außer Euro)2D kostenlos`
- `fx_percent` = 0: 
  - `in Euro kostenlos ⏎ innerhalb des EWR2B in EWR-Währung2C (außer Euro)2D kostenlos`
  - `innerhalb des EWR2B in EWR-Währung2C (außer Euro)2D kostenlos ⏎ innerhalb des EWR2B in Nicht-EWR-Währung2C, 2F kostenlos`
  - `innerhalb des EWR2B in Nicht-EWR-Währung2C, 2F kostenlos ⏎ außerhalb des EWR2B in jeder Fremdwährung2F kostenlos`
  - `in Euro kostenlos seitens der DKB AG2N ⏎ innerhalb des EWR2B in EWR-Währung2C (außer Euro)2D kostenlos seitens der DKB AG2N`
  - `innerhalb des EWR2B in EWR-Währung2C (außer Euro)2D kostenlos seitens der DKB AG2N ⏎ innerhalb des EWR2B in Nicht-EWR-Währung2C, 2F kostenlos seitens der DKB AG2N`
  - `innerhalb des EWR2B in Nicht-EWR-Währung2C, 2F kostenlos seitens der DKB AG2N ⏎ außerhalb des EWR2B in jeder Fremdwährung2F kostenlos seitens der DKB AG2N`

## r19 (VERIFY): Ich habe ein HVB AktivKonto. Was kostet eine Abhebung von 300 EUR mit der HVB Mastercard an einem fremden Automaten?

`hvb:HVB Mastercard AktivKonto`, page 5. Hand: VERIFY: 'Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold im HVB AktivKonto und HVB PlusKonto 2,50 EUR' -> flat 2.50; plain HVB Mastercard 2% mind. 5 -> 6.00. wallet entry matched by words, so 'HVB Mastercard / HVB AktivKonto' or '(HVB AktivKonto)' both resolve

Expected cost 2.50 EUR: correct, the open question was if the withdrawal was is in EU/EWR countries

- `percent` = null: check the page states no number for it
- `min_eur` = 2.50: 
  - `und der Cash Group kostenfrei Beleghafte Aufträge zwei Geschäftstage ⏎ – an allen anderen Geldautomaten 2,50 EUR Beleglose Aufträge einen Geschäftstag`
  - `– Beleghafte Aufträge 1,00 EUR ⏎ – bei allen anderen Geldautomaten 2,50 EUR`
  - `c) girocard (Debitkarte ohne Maestro) HVB StartKonto 0,90 EUR ⏎ – Bargeldauszahlung mit der Debitkarte am Geldautomaten HVB AktivKonto, HVB BasisKonto Aktiv 2,50 EUR`
  - `– Bargeldauszahlung mit der Debitkarte am Schalter fremder Ausnahme: HVB AktivKonto, HVB BasisKonto Aktiv, ⏎ Kreditinstitute oder an fremden Geldautomaten nicht möglich HVB BusinessKonto 4You 2,50 EUR`
  - `Sonderkonditionenvereinbarung für Verbraucher oder Nichtverbraucher oder sonstige Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold ⏎ Preisvereinbarung). im HVB AktivKonto und HVB PlusKonto 2,50 EUR`
  - `der UniCredit Group Ausnahme: ⏎ – bei HVB Platinum Hauptkonto, HVB Depot Global Konto, HVB BusinessKonto 4You 2,50 EUR`

## r20: Ich habe mit Revolut diesen Monat erst 400 EUR umgetauscht. Was kostet ein Einkauf über 300 EUR in den USA?

`revolut_standard`, page 5. Hand: 400 + 300 <= 1000 -> rev FX 0.00; c24/dkb/tr 0.00; hvb 5.25; ing 6.60

Expected cost 0.00 EUR: yes, but also the question is if the user has euros or dollars on hand

- `fx_percent` = 0.5: 
  - `Standard:Wechsellimit von 1.000 EUR pro Monat. Für jeden zusätzlichen ⏎ Währungswechsel fällt eine faire Nutzungsgebühr von 0,5 % an.`
  - `Plus: Wechsellimit von 3.000 EUR pro Monat. Für jeden zusätzlichen ⏎ Währungswechsel fällt eine faire Nutzungsgebühr von 0,5 % an.`
- `fx_free_eur` = 1000: 
  - `zusätzlichen Betrag eine faire Nutzungsgebühr berechnet. Diese Limits sind: ⏎ Standard:Wechsellimit von 1.000 EUR pro Monat. Für jeden zusätzlichen`


import json
import logging

from cardcost.logs import JsonFormatter, new_run_id, redact


def test_redacts_iban_email_phone():
    s = redact("IBAN DE89 3704 0044 0532 0130 00, mail max@bank.de, Tel +49 30 1234567 oder 030/1234567")
    assert "DE89" not in s and "max@bank.de" not in s and "1234567" not in s
    assert s.count("[IBAN]") == 1 and "[EMAIL]" in s and s.count("[PHONE]") == 2


def test_redact_keeps_money():
    assert redact("Kosten 1.234,56 EUR und 2,0 %") == "Kosten 1.234,56 EUR und 2,0 %"


def test_json_line_has_run_id_and_is_redacted():
    run_id = new_run_id()
    rec = logging.LogRecord("cardcost", logging.INFO, __file__, 1, "contact %s", ("a@b.de",), None)
    rec.tokens = 12
    line = json.loads(JsonFormatter().format(rec))
    assert line["run_id"] == run_id and line["tokens"] == 12 and line["msg"] == "contact [EMAIL]"

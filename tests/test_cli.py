from decimal import Decimal

from cardcost import db
from cardcost.cli import main
from cardcost.models import FeeSchedule


def test_review_list_and_edit_roundtrip(tmp_path, capsys):
    path = str(tmp_path / "t.db")
    conn = db.connect(path)
    fee = FeeSchedule(card="gamma_card", percent=None, source_file="gamma_card.pdf", source_page=1, confidence=0.9)
    eid = db.save_extraction(conn, fee, status="needs_review", run_id="r", prompt_version="v1")
    assert main(["--db", path, "review", "list"]) == 0
    assert f"#{eid} gamma_card" in capsys.readouterr().out
    rc = main(
        [
            "--db",
            path,
            "review",
            "edited",
            str(eid),
            "--set",
            "percent=2,5",
            "--set",
            "min_eur=4",
            "--quote",
            "2,5 % mindestens 4,00 EUR",
            "--reviewer",
            "ersan",
        ]
    )
    assert rc == 0
    [fixed] = db.reviewed_fees(db.connect(path), "gamma_card")
    assert (fixed.percent, fixed.min_eur) == (Decimal("2.5"), Decimal("4"))
    assert main(["--db", path, "review", "approved", str(eid)]) == 2  # one decision per extraction


def test_wallet(tmp_path, capsys):
    path = str(tmp_path / "t.db")
    assert main(["--db", path, "wallet", "beta_card:Gold", "alpha_card"]) == 0
    assert capsys.readouterr().out.split() == ["alpha_card", "beta_card:Gold"]

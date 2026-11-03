import argparse
import json
import sqlite3
import sys
from decimal import Decimal

from cardcost import db
from cardcost.advisor import build_advisor, corpus_paths, parse_scenario, parse_usage
from cardcost.answer import answer, render_table
from cardcost.calc import matrix, rank
from cardcost.ingest import process_job
from cardcost.logs import new_run_id, setup_logging
from cardcost.models import NUMERIC_FIELDS, FeeSchedule, Usage
from cardcost.numbers import parse_german_decimal


def cmd_ingest(conn, args) -> None:
    for path in args.paths:
        db.enqueue_ingest(conn, path)
    for row in conn.execute("SELECT id, path FROM ingest_job WHERE status = 'queued'").fetchall():
        print(f"job {row['id']} {row['path']}: {process_job(conn, row['id'])}")
    for p in corpus_paths(conn):
        print(f"corpus: {p}")


def cmd_products(conn, args) -> None:
    advisor = build_advisor(conn, args.mode)
    advisor.wallet = sorted({p.card_id for p in advisor.retriever.passages})
    for label, fee in advisor.resolve("Bargeld Entgelt").items():
        print(label if fee else f"{label}  (no fees extracted, see `cardcost review list`)")


def cmd_wallet(conn, args) -> None:
    for entry in args.entries:
        db.wallet_add(conn, entry)
    print("\n".join(db.wallet(conn)) or "wallet empty: every ingested card/product is compared")


def ask_usage(fees: dict[str, FeeSchedule | None], used: dict[str, Usage], ask=input) -> dict[str, Usage]:
    """Ask how much of each free allowance is used, for cards that have one and were not given via --used."""
    for label, fee in fees.items():
        if not fee or (fee.free_count is None and fee.free_amount_eur is None):
            continue
        if label in used or label.partition(":")[0] in used:
            continue
        limit = " / ".join(
            x
            for x in (fee.free_count and f"{fee.free_count} free", fee.free_amount_eur and f"{fee.free_amount_eur} EUR")
            if x
        )
        period = fee.conditions or "per period"
        count = int(ask(f"{label} ({limit}, {period}): withdrawals so far? "))
        eur = parse_german_decimal(ask(f"{label}: EUR withdrawn so far? ")) if fee.free_amount_eur is not None else None
        used[label] = Usage(count=count, eur=eur)
    return used


def cmd_ask(conn, args) -> None:
    run_id = new_run_id()
    used = parse_usage(args.used)
    scenario = parse_scenario(
        args.question, amount_eur=args.amount, kind=args.kind, country=args.country, days=args.days
    )
    advisor = build_advisor(conn, args.mode)
    fees = advisor.resolve(args.question)
    if scenario.kind == "cash" and sys.stdin.isatty():
        used = ask_usage(fees, used)
    scenario = scenario.model_copy(update={"used": used})
    table = rank(fees, scenario)
    text, source = answer(args.question, scenario, table, advisor.fees, advisor.llm)
    print(f"{text}\n\n{render_table(table)}\n\n(answer: {source}, run {run_id}, scenario {scenario.model_dump_json()})")
    if pending := db.pending_reviews(conn):
        print(f"{len(pending)} extraction(s) waiting for review: cardcost review list")


def cmd_matrix(conn, args) -> None:
    advisor = build_advisor(conn, args.mode)
    fees = advisor.resolve("Bargeldauszahlung Fremdwährung")
    for kind in ("cash", "purchase"):
        for country in args.countries.split(","):
            bands = matrix(fees, kind, country, args.max)
            print(f"{kind:8} {country}: " + "; ".join(f"{a}-{b} EUR -> {w}" for a, b, w in bands))


def cmd_review(conn, args) -> None:
    if args.action == "list":
        for r in db.pending_reviews(conn):
            fee = json.loads(r["fee_json"]) if r["fee_json"] else {}
            nums = {k: fee.get(k) for k in NUMERIC_FIELDS if fee.get(k) is not None}
            print(
                f"#{r['id']} {r['card']} {r['product'] or ''} conf={r['confidence']} {nums}\n"
                f"    quote: {r['quote']}\n    page: {r['source_file']} p.{r['page']}  error: {r['error'] or '-'}"
            )
        return
    edits = dict(kv.split("=", 1) for kv in args.set)
    edits = {k: str(Decimal(v.replace(",", "."))) if k != "product" else v for k, v in edits.items()}
    db.record_decision(conn, args.id, args.action, args.reviewer, edits or None, quote=args.quote)
    print(f"#{args.id}: {args.action} by {args.reviewer}")


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    ap = argparse.ArgumentParser(prog="cardcost", description="German credit-card cost advisor")
    ap.add_argument("--db", default=None, help="SQLite path (default $CARDCOST_DB or cardcost.db)")
    ap.add_argument("--mode", default="hybrid", choices=["bm25", "vector", "hybrid"])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest", help="queue PDFs and process queued ingest jobs")
    p.add_argument("paths", nargs="*")
    sub.add_parser("products", help="list card products found in the documents")
    p = sub.add_parser("wallet", help="choose which cards/products you own, e.g. beta_card:Gold")
    p.add_argument("entries", nargs="*")
    p = sub.add_parser("ask", help='e.g. "Welche Karte ist am günstigsten für 300 EUR Bargeld in den USA?"')
    p.add_argument("question")
    p.add_argument("--amount", type=Decimal)
    p.add_argument("--kind", choices=["cash", "purchase"])
    p.add_argument("--country", help="ISO code, e.g. US")
    p.add_argument("--days", type=int, help="days until repayment (adds cash-advance interest)")
    p.add_argument(
        "--used",
        action="append",
        default=[],
        help="withdrawals already made this allowance period: card=N or card=N:EUR (asked interactively if omitted)",
    )
    p = sub.add_parser("matrix", help="which card wins for which amount and scenario")
    p.add_argument("--countries", default="DE,FR,US")
    p.add_argument("--max", type=int, default=2000)
    p = sub.add_parser("review", help="human review of extractions")
    p.add_argument("action", choices=["list", "approved", "edited", "rejected"])
    p.add_argument("id", type=int, nargs="?")
    p.add_argument("--reviewer", default="human")
    p.add_argument("--set", action="append", default=[], help="field=value, e.g. min_eur=6,50")
    p.add_argument("--quote", help="exact source sentence for edited values")
    args = ap.parse_args(argv)
    if args.cmd == "review" and args.action != "list" and args.id is None:
        ap.error("review approved|edited|rejected needs an extraction id")
    conn = db.connect(args.db)
    handler = {
        "ingest": cmd_ingest,
        "products": cmd_products,
        "wallet": cmd_wallet,
        "ask": cmd_ask,
        "matrix": cmd_matrix,
        "review": cmd_review,
    }[args.cmd]
    try:
        handler(conn, args)
    except sqlite3.IntegrityError:
        print("error: this extraction already has a review decision", file=sys.stderr)
        return 2
    except (ValueError, KeyError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

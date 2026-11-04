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
from cardcost.models import EUROZONE, HOME, NUMERIC_FIELDS, FeeSchedule, Scenario, Usage
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


def ask_usage(
    fees: dict[str, FeeSchedule | None], used: dict[str, Usage], scenario: Scenario, ask=input
) -> dict[str, Usage]:
    """Ask how much of each allowance that matters for this scenario is used, unless given via --used."""
    for label, fee in fees.items():
        if not fee or label in used or label.partition(":")[0] in used:
            continue
        cash = scenario.kind == "cash" and (fee.free_count is not None or fee.free_amount_eur is not None)
        fx = scenario.foreign_currency and fee.fx_free_eur is not None
        if not (cash or fx):
            continue
        if not cash:  # the withdrawal count only matters for cash
            fx_eur = parse_german_decimal(ask(f"{label} (Wechsellimit {fee.fx_free_eur} EUR): EUR exchanged so far? "))
            used[label] = Usage(count=0, fx_eur=fx_eur)
            continue
        limit = " / ".join(
            x
            for x in (fee.free_count and f"{fee.free_count} free", fee.free_amount_eur and f"{fee.free_amount_eur} EUR")
            if x
        )
        period = fee.conditions or "per period"
        count = int(ask(f"{label} ({limit}, {period}): withdrawals so far? "))
        eur = parse_german_decimal(ask(f"{label}: EUR withdrawn so far? ")) if fee.free_amount_eur is not None else None
        fx_eur = (
            parse_german_decimal(ask(f"{label} (Wechsellimit {fee.fx_free_eur} EUR): EUR exchanged so far? "))
            if fx
            else None
        )
        used[label] = Usage(count=count, eur=eur, fx_eur=fx_eur)
    return used


def choose_products(
    conn, fees: dict[str, FeeSchedule | None], choices: dict[str, list[FeeSchedule]], ask=input
) -> dict[str, FeeSchedule | None]:
    """Let the user pick the product a wallet entry means; the pick replaces the entry in the saved wallet."""
    wallet = db.wallet(conn)
    for entry, options in choices.items():
        print(f"{entry}: which product do you have?")
        for i, f in enumerate(options, 1):
            print(f"  {i}) {f.product}")
        pick = options[int(ask("number: ")) - 1]
        chosen = f"{entry.partition(':')[0]}:{pick.product}"
        fees = {k: v for k, v in fees.items() if k != entry} | {chosen: pick}
        wallet = [chosen if e == entry else e for e in wallet]
    db.wallet_set(conn, wallet)
    return fees


def cmd_ask(conn, args) -> None:
    run_id = new_run_id()
    used = parse_usage(args.used)
    scenario = parse_scenario(
        args.question, amount_eur=args.amount, kind=args.kind, country=args.country, days=args.days
    )
    advisor = build_advisor(conn, args.mode)
    fees = advisor.resolve(args.question)
    if sys.stdin.isatty():
        fees = choose_products(conn, fees, advisor.choices)
        used = ask_usage(fees, used, scenario)
    elif advisor.choices:
        print(
            "ambiguous products, choose one with `cardcost wallet`: "
            + "; ".join(f"{e} -> {', '.join(f.product for f in fs)}" for e, fs in advisor.choices.items())
        )
    scenario = scenario.model_copy(update={"used": used})
    table = rank(fees, scenario)
    text, source = answer(args.question, scenario, table, fees, advisor.llm)
    print(f"{text}\n\n{render_table(table)}\n\n(answer: {source}, run {run_id}, scenario {scenario.model_dump_json()})")
    if pending := db.pending_reviews(conn):
        print(f"{len(pending)} extraction(s) waiting for review: cardcost review list")


def cmd_matrix(conn, args) -> None:
    advisor = build_advisor(conn, args.mode)
    fees = advisor.resolve("Bargeldauszahlung Fremdwährung")
    countries = args.countries.split(",")
    used = parse_usage(args.used)
    if sys.stdin.isatty():  # one probe scenario that triggers both the cash and the FX questions
        foreign = next((c for c in countries if c.upper() not in EUROZONE), HOME)
        used = ask_usage(fees, used, Scenario(kind="cash", amount_eur=Decimal(1), country=foreign))
    for kind in ("cash", "purchase"):
        for country in countries:
            bands = matrix(fees, kind, country, args.max, used)
            print(f"{kind:8} {country}: " + "; ".join(f"{a}-{b} EUR -> {w}" for a, b, w in bands))
    allowance = ("free_count", "free_amount_eur", "fx_free_eur")
    state = Scenario(kind="cash", amount_eur=Decimal(1), used=used)
    assumed = [
        label
        for label, fee in fees.items()
        if fee and any(getattr(fee, f) is not None for f in allowance) and not state.usage_for(label)
    ]
    if assumed:
        print("allowance assumed used up (pass --used): " + ", ".join(assumed))


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
    p.add_argument("--used", action="append", default=[], help="allowance usage so far: card=N[:EUR[:FX_EUR]]")
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

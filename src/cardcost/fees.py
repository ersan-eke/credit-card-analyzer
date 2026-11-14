"""The fees file: each price list's fees, extracted once at ingest (ADR 0001) and read by every question."""

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from cardcost.extract import PROMPT_VERSION, extract_fees
from cardcost.ingest import lost_numbers, passages_from_pages, read_text
from cardcost.models import FeeSchedule, Passage
from cardcost.retrieval import E5Embedder, Retriever

CATALOG_DOCS = Path("catalog/docs")
CATALOG_FEES = Path("catalog/fees.json")
# Always retrieved for extraction, so the fee pages reach the extractor whatever else the price list contains.
# One line per fee, with every name the price lists use for it; a new synonym is a one-line change.
FEE_QUERY = " ".join(
    [
        "Bargeldauszahlung Bargeldverfügung Abhebung Geldautomat Entgelt Gebühr",
        "Fremdwährung Auslandseinsatzentgelt Währungsumrechnungsentgelt Wechselgebühr Wechsellimit",
        "Geldautomatenbetreiber Sollzinssatz",
    ]
)


def fee_passages(retriever: Retriever, card_id: str) -> list[Passage]:
    # shortcut: one extra passage per 3 pages, so long price lists (HVB, Revolut) keep their fee pages in context;
    # measured on the real golden set: context recall 0.90 -> 0.95 (hybrid) for ~28 % more passages
    pages = max((p.page for p in retriever.passages if p.card_id == card_id), default=0)
    found = retriever.search(FEE_QUERY, card_id, max(3, pages // 3))
    return sorted(found, key=lambda p: p.id)


def read_fees(paths: Iterable[Path] = (CATALOG_FEES,)) -> dict[str, list[FeeSchedule]]:
    """Card id -> its products. Every fee is validated again on load: numbers must come from the stored quote."""
    out: dict[str, list[FeeSchedule]] = {}
    for path in paths:
        if not path.exists():
            raise RuntimeError(f"{path} not found: run `cardcost ingest` to extract the fees")
        for card, entry in json.loads(path.read_text()).items():
            out[card] = [FeeSchedule.model_validate(f) for f in entry["fees"]]
    return out


def update_fees(paths: list[Path], fees_path: Path, llm, conn, mode: str = "hybrid") -> dict[str, str]:
    """Extract the price lists whose file or prompt changed since the fees file was written; return card id -> what
    happened ("extracted", "no fees found" or "flagged: ..."). A card with no fees (extraction failed) is retried.
    Unchanged lists cost no LLM call and leave the file as is. A list whose converted text lost numbers is flagged,
    not sent to the LLM."""
    entries = json.loads(fees_path.read_text()) if fees_path.exists() else {}
    stale = {}
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entry = entries.get(path.stem)
        if not (entry and entry["fees"] and (entry["sha256"], entry["prompt_version"]) == (digest, PROMPT_VERSION)):
            stale[path] = digest
    done, passages = {}, []
    for path in list(stale):
        pages = read_text(path)
        if lost := lost_numbers(path, pages):
            done[path.stem] = f"flagged: numbers lost in extraction: {', '.join(lost)}"
            del stale[path]
        else:
            passages += passages_from_pages(path.stem, path.name, pages)
    if stale:
        retriever = Retriever(passages, mode=mode, embedder=None if mode == "bm25" else E5Embedder())
        for path, digest in stale.items():
            fees = extract_fees(path.stem, fee_passages(retriever, path.stem), llm, conn)
            done[path.stem] = "extracted" if fees else "no fees found"
            if not fees and entries.get(path.stem):  # a failed extraction must not wipe the fees we have
                continue
            entries[path.stem] = {
                "sha256": digest,
                "prompt_version": PROMPT_VERSION,
                "fees": [json.loads(f.model_dump_json()) for f in fees],
            }
            # written per card, so a run that dies on a rate limit keeps what it has; a rerun resumes
            fees_path.parent.mkdir(parents=True, exist_ok=True)
            fees_path.write_text(json.dumps(entries, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return done

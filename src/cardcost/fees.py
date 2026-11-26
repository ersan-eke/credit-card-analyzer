"""The fees file: each price list's fees, extracted once at ingest (ADR 0001) and read by every question."""

import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path

from cardcost.extract import PROMPT_VERSION, TooLong, extract_fees
from cardcost.ingest import lost_numbers, read_text
from cardcost.models import FeeSchedule

CATALOG_DOCS = Path("catalog/docs")
CATALOG_FEES = Path("catalog/fees.json")


def read_fees(paths: Iterable[Path] | None = None) -> dict[str, list[FeeSchedule]]:
    """Card id -> its products. Every fee is validated again on load: numbers must come from the stored quote.
    Default file: $CARDCOST_FEES, else catalog/fees.json."""
    paths = paths or (Path(os.environ.get("CARDCOST_FEES", CATALOG_FEES)),)
    out: dict[str, list[FeeSchedule]] = {}
    for path in paths:
        if not path.exists():
            raise RuntimeError(f"{path} not found: run `cardcost ingest` to extract the fees")
        for card, entry in json.loads(path.read_text()).items():
            out[card] = [FeeSchedule.model_validate(f) for f in entry["fees"]]
    return out


def update_fees(paths: list[Path], fees_path: Path, llm, conn) -> dict[str, str]:
    """Extract the price lists whose file or prompt changed since the fees file was written; return card id -> what
    happened ("extracted", "no fees found" or "flagged: ..."). A card with no fees (extraction failed) is retried.
    Unchanged lists cost no LLM call and leave the file as is. A list whose converted text lost numbers or is over the
    token budget is flagged, not sent to the LLM."""
    entries = json.loads(fees_path.read_text()) if fees_path.exists() else {}
    stale = {}
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entry = entries.get(path.stem)
        if not (entry and entry["fees"] and (entry["sha256"], entry["prompt_version"]) == (digest, PROMPT_VERSION)):
            stale[path] = digest
    done = {}
    for path, digest in stale.items():
        pages = read_text(path)
        if lost := lost_numbers(path, pages):
            done[path.stem] = f"flagged: numbers lost in extraction: {', '.join(lost)}"
            continue
        try:
            fees = extract_fees(path.stem, path.name, pages, llm, conn)
        except TooLong as e:
            done[path.stem] = f"flagged: {e}"
            continue
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

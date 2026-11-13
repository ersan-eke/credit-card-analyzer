import tomllib
from pathlib import Path

CATALOG_DIR = Path(__file__).parent.parent / "catalog"


def test_every_reviewed_copy_has_exactly_one_source():
    sources = tomllib.loads((CATALOG_DIR / "sources.toml").read_text())["source"]
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids))
    assert sorted(ids) == sorted(p.stem for p in (CATALOG_DIR / "docs").glob("*.pdf"))
    for s in sources:
        assert s["bank"] and s["url"].startswith("https://"), s

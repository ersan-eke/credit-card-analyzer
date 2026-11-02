from pathlib import Path

import numpy as np
import pytest

from cardcost.ingest import ingest_paths
from cardcost.models import Passage
from cardcost.retrieval import Retriever, rrf


def _p(i: int, text: str, card: str = "a") -> Passage:
    return Passage(id=f"{card}{i}", card_id=card, file=f"{card}.pdf", page=i, text=text)


def test_rrf_k60_maths():
    scores = rrf([["x", "y"], ["y", "z"]], k=60)
    assert scores["y"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["x"] == pytest.approx(1 / 61)
    assert max(scores, key=scores.get) == "y"


class FakeEmbedder:
    """Maps a text to a fixed vector by keyword, so hybrid tests are deterministic."""

    def embed(self, texts: list[str], kind: str) -> np.ndarray:
        vecs = np.array([[float("bargeld" in t.lower()), float("währung" in t.lower()), 0.1] for t in texts])
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


PS = [
    _p(1, "Jahresentgelt und Kontakt"),
    _p(2, "Bargeldauszahlungsentgelt 2,0 %"),
    _p(3, "Fremdwährungsentgelt 1,75 %"),
    _p(1, "Bargeld kostet hier 3 %", card="b"),
]


def test_bm25_exact_token_and_card_filter():
    r = Retriever(PS, mode="bm25")
    top = r.search("Fremdwährungsentgelt", card_id="a", k=1)
    assert top[0].page == 3
    assert all(p.card_id == "a" for p in r.search("Bargeld", card_id="a", k=3))


def test_vector_finds_compound_without_token_overlap():
    r = Retriever(PS, mode="vector", embedder=FakeEmbedder())
    assert r.search("Geld in fremder Währung", card_id="a", k=1)[0].page == 3


def test_hybrid_returns_k_from_both_lists():
    r = Retriever(PS, mode="hybrid", embedder=FakeEmbedder())
    top = r.search("Bargeld abheben", card_id="a", k=2)
    assert len(top) == 2 and top[0].page == 2


@pytest.mark.slow
def test_real_model_handles_german_compound():
    ps = ingest_paths(sorted((Path(__file__).parent.parent / "samples").glob("*.pdf")))
    from cardcost.retrieval import E5Embedder

    r = Retriever(ps, mode="vector", embedder=E5Embedder())
    top = r.search("Entgelt für Zahlungen in fremder Währung", card_id="alpha_card", k=1)
    assert top[0].page == 2

import re
from collections import defaultdict
from typing import Literal, Protocol

import numpy as np
from rank_bm25 import BM25Okapi

from cardcost.models import Passage

Mode = Literal["bm25", "vector", "hybrid"]


class Embedder(Protocol):
    def embed(self, texts: list[str], kind: Literal["query", "passage"]) -> np.ndarray:
        """Return L2-normalised row vectors."""
        ...


class E5Embedder:
    """Local multilingual model, no API key. E5 expects 'query: ' / 'passage: ' prefixes."""

    def __init__(self, model: str = "intfloat/multilingual-e5-small"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model)

    def embed(self, texts: list[str], kind: Literal["query", "passage"]) -> np.ndarray:
        return self.model.encode([f"{kind}: {t}" for t in texts], normalize_embeddings=True)


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, pid in enumerate(ranking, start=1):
            scores[pid] += 1 / (k + rank)
    return scores


class Retriever:
    def __init__(self, passages: list[Passage], mode: Mode = "hybrid", embedder: Embedder | None = None):
        if mode != "bm25" and embedder is None:
            raise ValueError(f"mode {mode!r} needs an embedder")
        self.passages, self.mode, self.embedder = passages, mode, embedder
        # one index per card: search is per card, and corpus-wide IDF makes the card's own name look rare
        self.bm25 = {
            card: (idx, BM25Okapi([tokenize(passages[i].text) for i in idx]))
            for card in {p.card_id for p in passages}
            for idx in [[i for i, p in enumerate(passages) if p.card_id == card]]
        }
        self.vectors = embedder.embed([p.text for p in passages], "passage") if embedder else None

    def _bm25_rank(self, query: str, idx: list[int]) -> list[int]:
        # zero-score passages share no token with the query; their order is noise, so RRF must not see them
        scores: dict[int, float] = {}
        for card_idx, index in self.bm25.values():
            scores.update(zip(card_idx, index.get_scores(tokenize(query)), strict=True))
        return sorted((i for i in idx if scores[i] > 0), key=lambda i: -scores[i])

    def _vector_rank(self, query: str, idx: list[int]) -> list[int]:
        q = self.embedder.embed([query], "query")[0]
        scores = self.vectors @ q
        return sorted(idx, key=lambda i: -scores[i])

    def search(self, query: str, card_id: str | None = None, k: int = 3) -> list[Passage]:
        idx = [i for i, p in enumerate(self.passages) if card_id is None or p.card_id == card_id]
        if self.mode == "bm25":
            hits = self._bm25_rank(query, idx)
            order = hits + [i for i in idx if i not in hits]
        elif self.mode == "vector":
            order = self._vector_rank(query, idx)
        else:
            fused = rrf([self._bm25_rank(query, idx), self._vector_rank(query, idx)])
            order = sorted(idx, key=lambda i: -fused.get(i, 0))
        return [self.passages[i] for i in order[:k]]

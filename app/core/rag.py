import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi


@dataclass
class Chunk:
    chunk_id: str
    tenant_id: str
    text: str


class HybridRAG:
    def __init__(self) -> None:
        self.chunks = [
            Chunk("pol-001", "tenant_demo", "Batch LOT-88392 safety protocol requires temperature review before release."),
            Chunk("pol-002", "tenant_demo", "A Tier 3 mutation requires asynchronous human-in-the-loop approval."),
            Chunk("pol-003", "tenant_demo", "Obfuscated PII such infomation@example[dot]com must be rejected or redacted."),
            Chunk("pol-004", "tenant_demo", "The 50K load target requires p95 below 450 ms and p99 below 590 ms."),
        ]

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9_-]+", text.lower())

    def retrieve(self, tenant_id: str, query: str, limit: int = 4) -> list[tuple[Chunk, float]]:
        scoped = [chunk for chunk in self.chunks if chunk.tenant_id == tenant_id]
        if not scoped:
            return []
        corpus = [self.tokenize(chunk.text) for chunk in scoped]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(self.tokenize(query))
        ranked = sorted(zip(scoped, scores), key=lambda item: item[1], reverse=True)
        return [(chunk, float(score)) for chunk, score in ranked[:limit]]

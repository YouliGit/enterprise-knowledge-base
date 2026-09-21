"""检索管线的数据结构：阶段追踪 StageTrace 显式标注每一步的量纲与阈值适用性。"""
from dataclasses import dataclass, field
from typing import Optional


# 量纲常量：score 在管线里每覆盖一次量纲就换一次，必须显式声明
SCALE_COSINE = "cosine"      # 余弦相似度 0~1，相关片段实测 0.46~0.77，阈值过滤：是
SCALE_BM25 = "bm25"          # BM25 分数，无上界，阈值过滤：否
SCALE_RRF = "rrf"            # RRF 名次分 约0.016~0.033，只表示名次先后，阈值过滤：否
SCALE_RERANK = "rerank"      # 重排相关分 0~1，相关片段实测 0.14~0.20，阈值过滤：是

SCALE_DESC = {
    SCALE_COSINE: {"name": "余弦相似度", "range": "0~1", "threshold": True},
    SCALE_BM25: {"name": "BM25分数", "range": "无上界", "threshold": False},
    SCALE_RRF: {"name": "RRF名次分", "range": "约0.016~0.033", "threshold": False},
    SCALE_RERANK: {"name": "重排相关分", "range": "0~1", "threshold": True},
    "none": {"name": "-", "range": "-", "threshold": False},
}


@dataclass
class Hit:
    """一条带分数的命中"""
    chunk_id: int
    parent_id: Optional[int]
    content: str
    score: float
    scale: str = SCALE_COSINE
    rank: int = 0

    def to_dict(self, preview: int = 80) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "parent_id": self.parent_id,
            "score": round(self.score, 4),
            "scale": self.scale,
            "rank": self.rank,
            "preview": (self.content or "")[:preview],
        }


@dataclass
class StageTrace:
    """一个检索阶段的追踪：查询词、量纲、阈值是否适用、命中明细"""
    stage: str                      # rewrite/vector/bm25/rrf/backfill/rerank
    query: str = ""
    scale: str = "none"
    threshold: Optional[float] = None
    threshold_applies: bool = False
    note: str = ""
    cost_ms: int = 0
    hits: list = field(default_factory=list)

    def to_dict(self) -> dict:
        meta = SCALE_DESC.get(self.scale, SCALE_DESC["none"])
        return {
            "stage": self.stage,
            "query": self.query,
            "scale": self.scale,
            "scale_name": meta["name"],
            "scale_range": meta["range"],
            "threshold": self.threshold,
            "threshold_applies": self.threshold_applies or meta["threshold"],
            "threshold_note": "按量纲配置阈值" if meta["threshold"] else "本次不适用（量纲不可比）",
            "note": self.note,
            "cost_ms": self.cost_ms,
            "hits": self.hits,
        }


@dataclass
class RetrievedContext:
    """最终给模型的上下文（父块），带各量纲分数便于前端展示"""
    chunk_id: int                  # 父块ID
    content: str
    scores: dict = field(default_factory=dict)   # {"cosine":..,"bm25":..,"rrf":..,"rerank":..}
    rank: int = 0

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "rank": self.rank,
            "content": self.content,
            "scores": {k: round(v, 4) for k, v in self.scores.items() if v is not None},
        }


@dataclass
class RetrievalOutput:
    contexts: list = field(default_factory=list)      # list[RetrievedContext]
    traces: list = field(default_factory=list)        # list[StageTrace]
    rewritten_queries: list = field(default_factory=list)
    rounds: int = 1

    def traces_dict(self) -> list:
        return [t.to_dict() for t in self.traces]

    def contexts_dict(self) -> list:
        return [c.to_dict() for c in self.contexts]

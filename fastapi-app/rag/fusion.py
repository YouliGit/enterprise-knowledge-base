"""RRF 倒数排名融合：两路检索的量纲不同（余弦0~1 / BM25无上界），分数不能直接加，
RRF 只看名次不看分数正是为此设计。融合分 约 1/(60+rank)，即 0.016~0.033。"""


def rrf_fuse(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    """多路排名融合。

    :param rankings: 每一路按分数降序排好的 chunk_id 列表
    :param k: RRF 常数，默认 60
    :return: {chunk_id: rrf_score}
    """
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return dict(sorted(fused.items(), key=lambda x: x[1], reverse=True))


def dedupe_keep_score(pairs: list[tuple[int, float]]) -> dict[int, float]:
    """同 chunk 多查询命中时保留最高分（量纲内比较，不跨量纲）。"""
    best: dict[int, float] = {}
    for cid, s in pairs:
        if cid not in best or s > best[cid]:
            best[cid] = s
    return best

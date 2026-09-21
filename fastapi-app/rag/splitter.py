"""递归分块 / 父子分块。

片段小则命中准但上下文不全，片段大则上下文完整但难命中。
切两遍：只把子块向量化参与检索（小块用来找），命中后回填整个父块给模型生成（大块用来答）。
"""
import json
import re

from models import SplitStrategy


def _separators(strategy: SplitStrategy) -> list[str]:
    try:
        seps = json.loads(strategy.separators_json or "[]")
        if isinstance(seps, list) and seps:
            return [str(s).replace("\\n", "\n").replace("\\t", "\t") for s in seps]
    except Exception:
        pass
    return ["\n\n", "\n", "。", "；", "，", " "]


def _merge_slices(slices: list[str], chunk_size: int, overlap: int) -> list[str]:
    """把切出的碎片合并为不超过 chunk_size 的块，块间保留 overlap 字符重叠。"""
    chunks: list[str] = []
    buf = ""
    for piece in slices:
        piece = piece.strip()
        if not piece:
            continue
        if len(buf) + len(piece) + 1 <= chunk_size:
            buf = (buf + "\n" + piece).strip()
        else:
            if buf:
                chunks.append(buf)
            if len(piece) > chunk_size:
                # 单片超长则硬切
                step = max(chunk_size - overlap, 1)
                for i in range(0, len(piece), step):
                    part = piece[i:i + chunk_size]
                    if len(part) >= 20 or i == 0:
                        chunks.append(part)
                buf = ""
            else:
                buf = piece
    if buf:
        chunks.append(buf)
    # 相邻块加重叠
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for prev, cur in zip(chunks, chunks[1:]):
            tail = prev[-overlap:]
            overlapped.append(tail + cur if cur and not cur.startswith(tail) else cur)
        return overlapped
    return chunks


def recursive_split(text: str, chunk_size: int = 500, overlap: int = 50, separators: list[str] | None = None) -> list[str]:
    """按分隔符从粗到细递归切分。"""
    text = re.sub(r"\r\n", "\n", text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    seps = [s for s in (separators or ["\n\n", "\n", "。", "；", "，", " "]) if s]
    # 找到第一个存在的分隔符切一层
    for i, sep in enumerate(seps):
        if sep and sep in text:
            slices = [s for s in text.split(sep)]
            finer: list[str] = []
            for s in slices:
                if len(s) > chunk_size and i + 1 < len(seps):
                    finer.extend(recursive_split(s, chunk_size, overlap, seps[i + 1:]))
                else:
                    finer.append(s)
            return _merge_slices(finer, chunk_size, overlap)
    return _merge_slices([text], chunk_size, overlap)


def split_by_strategy(text: str, strategy: SplitStrategy) -> dict:
    """按切分策略切块。

    返回 {"parents": [...], "children": [{"content","parent_index"}]}
    - recursive:     无父块，children 即最终块（parent_index=-1，入库时 parent_id=NULL）
    - parent_child:  先切父块（大，用来答），再每个父块切子块（小，用来找）
    """
    sep = _separators(strategy)
    if strategy.mode == "parent_child":
        parents = recursive_split(
            text, strategy.parent_chunk_size or 1500, strategy.parent_chunk_overlap or 100, sep
        )
        children: list[dict] = []
        for pi, parent in enumerate(parents):
            subs = recursive_split(parent, strategy.chunk_size or 500, strategy.chunk_overlap or 50, sep)
            for sub in subs:
                children.append({"content": sub, "parent_index": pi})
        return {"parents": parents, "children": children}
    chunks = recursive_split(text, strategy.chunk_size or 500, strategy.chunk_overlap or 50, sep)
    return {"parents": [], "children": [{"content": c, "parent_index": -1} for c in chunks]}

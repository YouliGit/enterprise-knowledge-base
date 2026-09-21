"""jieba 中文分词 BM25：向量认识同义词但认不出精确型号，BM25 相反，两路互补。

smart_tokenize 会把 GTE3000 拆出 gte 和 3000，让「型号不带连字符」也能被精确命中。
"""
import math
import re
from collections import Counter

import jieba

_ASCII_ALNUM = re.compile(r"[0-9a-zA-Z]+")
jieba.setLogLevel(60)  # 关闭建库日志


def smart_tokenize(text: str) -> list[str]:
    """中文 jieba 分词 + ASCII 字母数字串二次拆分（全小写）。

    例：'GTE-3000光模块' -> ['gte', '3000', '光', '模块']（jieba结果再拆字母数字）
    """
    tokens: list[str] = []
    for tok in jieba.lcut((text or "").lower()):
        tok = tok.strip()
        if not tok:
            continue
        if re.fullmatch(r"[0-9a-zA-Z]+", tok):
            # 纯字母数字串：拆出字母段与数字段，GTE3000 -> gte / 3000
            pieces = re.findall(r"[0-9]+|[a-zA-Z]+", tok)
            tokens.extend(pieces)
        else:
            # 中英混合词：把其中的 ASCII 串单独拆出，中文词保留
            parts = re.findall(r"[0-9a-zA-Z]+|[^0-9a-zA-Z]+", tok)
            for p in parts:
                if re.fullmatch(r"[0-9a-zA-Z]+", p):
                    tokens.extend(re.findall(r"[0-9]+|[a-zA-Z]+", p))
                else:
                    tokens.append(p)
    return [t for t in tokens if t.strip()]


class BM25Okapi:
    """标准 Okapi BM25，纯 Python 实现，无第三方依赖。"""

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus_tokens)
        if self.corpus_size == 0:
            self.doc_freqs = []
            self.idf = {}
            self.doc_len = []
            self.avgdl = 0.0
            return
        self.doc_len = [len(d) for d in corpus_tokens]
        self.avgdl = sum(self.doc_len) / self.corpus_size
        df: Counter = Counter()
        self.doc_freqs = []
        for doc in corpus_tokens:
            freq = Counter(doc)
            self.doc_freqs.append(freq)
            for word in freq:
                df[word] += 1
        self.idf = {
            word: math.log(self.corpus_size - n + 0.5) - math.log(n + 0.5)
            for word, n in df.items()
        }

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        scores = [0.0] * self.corpus_size
        for qi in query_tokens:
            idf = self.idf.get(qi)
            if not idf or idf <= 0:
                continue
            for i, freq in enumerate(self.doc_freqs):
                if qi not in freq:
                    continue
                f = freq[qi]
                dl = self.doc_len[i] or 1
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1.0))
                scores[i] += idf * f * (self.k1 + 1) / denom
        return scores


class BM25Index:
    """对一个知识库的子块集合建 BM25 索引：ids 与 corpus 对齐。"""

    def __init__(self, chunk_ids: list[int], contents: list[str]):
        self.chunk_ids = chunk_ids
        self.contents = contents
        self.tokenized = [smart_tokenize(c) for c in contents]
        self.engine = BM25Okapi(self.tokenized)

    def search(self, query: str, top_k: int = 8) -> list[tuple[int, float]]:
        """返回 [(chunk_id, bm25_score)]，按分数降序。分数无上界，调用方不得做阈值过滤。"""
        q = smart_tokenize(query)
        if not q or not self.chunk_ids:
            return []
        scores = self.engine.get_scores(q)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [(self.chunk_ids[i], scores[i]) for i in order if scores[i] > 0]

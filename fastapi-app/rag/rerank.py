"""自写 LangChain 重排组件：百炼重排接口不在 OpenAI 兼容模式下，
包装成 BaseDocumentCompressor，作为标准组件接入检索链路（粗筛之后执行，候选上限 20 条）。"""
import time
from typing import Any, Optional, Sequence

import httpx
from pydantic import PrivateAttr

try:  # langchain-core 不同小版本导出位置不同，做兼容
    from langchain_core.documents.compressor import BaseDocumentCompressor
except Exception:
    from langchain_core.documents import BaseDocumentCompressor

from langchain_core.documents import Document


class DashScopeReranker(BaseDocumentCompressor):
    """DashScope 原生 text-rerank 接口 → 标准 BaseDocumentCompressor"""

    model: str = "gte-rerank-v2"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com"
    top_n: int = 5
    _last_raw_scores: list = PrivateAttr(default_factory=list)

    @property
    def last_raw_scores(self) -> list:
        return self._last_raw_scores

    def _endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/api/v1/services/rerank/text-rerank/text-rerank"

    def _call_native(self, query: str, docs: list[str], top_n: int) -> list[dict]:
        """调用 DashScope 原生接口，返回 [{"index":i,"relevance_score":s}]，按分数降序"""
        body = {
            "model": self.model,
            "input": {"query": query, "documents": docs},
            "parameters": {"return_documents": False, "top_n": top_n, "top_n_only_for_rerank": True},
        }
        resp = httpx.post(
            self._endpoint(),
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body,
            timeout=30,
        )
        data = resp.json()
        if resp.status_code != 200 or (data.get("code") and data.get("code") != ""):
            msg = data.get("message") or data.get("msg") or resp.text[:200]
            raise RuntimeError(f"重排接口失败: {msg}")
        results = (data.get("output") or {}).get("results") or []
        return results

    def compress_documents(self, documents: Sequence[Document], query: str,
                           callbacks: Optional[Any] = None, **kwargs: Any) -> Sequence[Document]:
        if not documents:
            return []
        docs = [d.page_content for d in documents]
        results = self._call_native(query, docs, self.top_n)
        out = []
        for r in results:
            idx = int(r.get("index", 0))
            score = float(r.get("relevance_score", 0.0))
            if idx < len(documents):
                doc = documents[idx]
                doc.metadata["rerank_score"] = score
                out.append(doc)
        return out

    async def acompress_documents(self, documents: Sequence[Document], query: str,
                                  callbacks: Optional[Any] = None, **kwargs: Any) -> Sequence[Document]:
        """异步版本：单引擎接口，直接线程池化同步调用即可"""
        import asyncio

        if not documents:
            self._last_raw_scores = []
            return []
        t0 = time.time()
        docs = [d.page_content for d in documents]
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, lambda: self._call_native(query, docs, len(docs)))
        self._last_raw_scores = [
            {"index": int(r.get("index", 0)), "relevance_score": float(r.get("relevance_score", 0.0))}
            for r in results
        ]
        out = []
        for r in results:
            idx = int(r.get("index", 0))
            score = float(r.get("relevance_score", 0.0))
            if idx < len(documents):
                doc = documents[idx]
                doc.metadata["rerank_score"] = score
                out.append(doc)
        return out

    async def rerank_texts(self, query: str, texts: list[str], top_n: int | None = None) -> list[dict]:
        """供管线直接调用：返回按分数降序的 [{"index","relevance_score"}]"""
        if not texts:
            return []
        results = self._call_native(query, texts, top_n or self.top_n)
        return [
            {"index": int(r.get("index", 0)), "relevance_score": float(r.get("relevance_score", 0.0))}
            for r in results
        ]

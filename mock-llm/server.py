"""Mock 大模型服务（测试沙箱专用，零第三方依赖，仅用 Python 标准库）。

为什么需要它：
    本项目真实推理全部走阿里云百炼（付费）。没有 API Key 时，「向量化入库 → 混合检索
    → 重排 → 问答生成 → Agentic 状态图 → LLM-as-judge 评测」这条主链路一步都跑不通，
    只能测到接口契约层。本服务在 Docker 沙箱内假扮三家云端模型，让全链路可以离线、
    确定性、可重复地端到端跑通与回归。

模拟的三个接口（与真实厂商协议一致，业务代码无需任何改动）：
    1. POST /v1/chat/completions           OpenAI 兼容，支持 stream 与 tool_calls（Function Calling）
    2. POST /v1/embeddings                 OpenAI 兼容，输出 EMBEDDING_DIM（默认 1024）维
    3. POST /api/v1/services/rerank/...    DashScope 原生重排协议

确定性设计（保证可重复、可断言）：
    - 向量：字符二元组 / ASCII 词 特征 + 带符号哈希投影（hashing trick）+ 特征截断
      到 TOPK 个。同类文本余弦相似度高（约 0.4~0.9），无关文本接近 0，因此
      「余弦阈值 / 重排阈值」这两处量纲过滤能被真实地驱动与验证。
    - 对话：按提示词模板里的中文标记识别任务（评估 / 自查 / 裁判 / 改写 / 生成），
      生成答案时从参考资料块 [1][2]… 里取内容作答，保证「有据可依」。
    - 工具：仅当问题里出现算式或「计算器」且本轮还没有工具结果时，才发起 tool_call，
      不会无限循环。

测试控制面：
    POST /_control  {"fail": {"chat": 2, "embedding": 1, "rerank": 1}, "reset": true}
        让接下来 N 次某类请求返回 500，用于验证业务侧的错误降级与友好报错。
    GET  /_control  查看当前故障注入状态与累计调用次数。
    POST /_control  {"reset": true}  清空故障注入与计数。

启动：python server.py   （默认 8000 端口，可用 MOCK_PORT 覆盖）
"""
import hashlib
import json
import math
import os
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------- 可调参数 ----------------
DIM = int(os.getenv("MOCK_EMBED_DIM", "1024"))   # 与 settings.EMBEDDING_DIM / vector(1024) 对齐
TOPK_FEATURES = int(os.getenv("MOCK_TOPK_FEATURES", "32"))  # 参与投影的最显著特征数
PORT = int(os.getenv("MOCK_PORT", "8000"))
LATENCY_MS = int(os.getenv("MOCK_LATENCY_MS", "0"))  # 人为延迟，用于压测/超时验证

CJK = re.compile(r"[\u4e00-\u9fff]")
ASCII_WORD = re.compile(r"[a-z0-9]+")
BIGRAM = re.compile(r"[\u4e00-\u9fa5]{2}")
CTX_LINE = re.compile(r"^\s*\[(\d+)\]\s*(.+)$", re.M)

_lock = threading.Lock()
_state = {
    "fail": {},          # {"chat": n, "embedding": n, "rerank": n}
    "calls": {"chat": 0, "embedding": 0, "rerank": 0},
    "errors": {"chat": 0, "embedding": 0, "rerank": 0},
}


# ---------------- 向量化（确定性 + 语义近似） ----------------

def _features(text: str) -> dict:
    """抽取特征并加权。

    权重设计模拟 IDF：多字特征（二元组 / ASCII 词）具区分度给高权，
    单字过于普遍给低权。这样「同主题文本」的共享特征能主导相似度。
    """
    t = (text or "").lower()
    feats: dict = {}
    for w in ASCII_WORD.findall(t):
        feats["w:" + w] = feats.get("w:" + w, 0.0) + 1.0
    for bg in BIGRAM.findall(t):
        feats["b:" + bg] = feats.get("b:" + bg, 0.0) + 1.0
    for ch in CJK.findall(t):
        feats["c:" + ch] = feats.get("c:" + ch, 0.0) + 0.25
    return feats


def embed(text: str, dim: int = DIM) -> list:
    """特征 → 带符号哈希投影 → L2 归一化。同一文本永远得到同一向量。"""
    feats = _features(text)
    if not feats:
        return [0.0] * dim
    # 特征截断：模拟稠密语义向量的「降维」，让长文档不会因特征过多而稀释相似度
    top = sorted(feats.items(), key=lambda kv: (-kv[1], kv[0]))[:TOPK_FEATURES]
    vec = [0.0] * dim
    for feat, weight in top:
        h = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if (h[4] & 1) else -1.0
        vec[idx] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0:
        return [0.0] * dim
    return [round(v / norm, 6) for v in vec]


def cosine(a: list, b: list) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(-1.0, min(1.0, dot))


# ---------------- 「对话」：按模板标记识别任务类型 ----------------

def _join(messages: list) -> str:
    return "\n".join(str(m.get("content") or "") for m in messages)


def _last_user(messages: list) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return str(m.get("content") or "")
    return ""


def _ctx_lines(prompt: str) -> list:
    return [c.strip() for _, c in CTX_LINE.findall(prompt) if c.strip() and c.strip() != "（无命中）"]


def _detect_task(prompt: str) -> str:
    """按内置 Prompt 模板里的中文特征词判断当前是哪个任务。"""
    if "rewrite_hint" in prompt and "sufficient" in prompt:
        return "evaluate"          # agent_evaluate_context
    if "答案质检器" in prompt or ("pass" in prompt and "编造" in prompt):
        return "self_check"        # agent_self_check
    if "逐条判断下列检索片段" in prompt or "scores" in prompt:
        return "judge_precision"   # judge_context_precision
    if "支撑的论断占全部论断的比例" in prompt:
        return "judge_faithfulness"
    if "跑题记0" in prompt or "相关程度" in prompt:
        return "judge_relevancy"
    if "查询扩展器" in prompt or "改写成3个不同表述" in prompt:
        return "multi_query"       # rewrite_multi_query
    if "指代消解" in prompt or "查询改写器" in prompt:
        return "coref"             # rewrite_coref
    if "文档生成器" in prompt or "假设" in prompt and "资料文本" in prompt:
        return "hyde"              # hyde_generate
    return "answer"                # 最终作答


def _compose_answer(messages: list) -> str:
    """生成答案：优先引用工具结果，否则从参考资料块里取内容作答（有据可依）。"""
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    if tool_msgs:
        raw = str(tool_msgs[-1].get("content") or "").strip().replace("\n", " ")
        return f"根据工具返回结果：{raw[:80]}。"
    prompt = _join(messages)
    ctx = _ctx_lines(prompt)
    question = _last_user(messages).strip()
    if not ctx:
        return "参考资料中没有找到相关内容，我无法回答这个问题。"
    head = re.split(r"[。；;\n]", ctx[0])[0][:70]
    extra = "，详见资料[2]" if len(ctx) > 1 else ""
    tail = f"（依据资料[1]{extra}）"
    if question:
        return f"针对「{question[:24]}」：{head}。{tail}"
    return f"{head}。{tail}"


def _calc_expr(text: str) -> str:
    m = re.search(r"(\d[\d\s\.\+\-\*/\(\)]{2,})\s*=", text)
    return m.group(1).strip() if m else ""


def _should_call_tool(messages: list, tools: list) -> dict:
    """是否需要发起工具调用：有 calculator 工具 + 问题含算式/计算器 + 本轮尚无工具结果。"""
    if not tools:
        return {}
    names = []
    for t in tools:
        fn = (t or {}).get("function") or {}
        if fn.get("name"):
            names.append(fn["name"])
    if "calculator" not in names:
        return {}
    if any(m.get("role") == "tool" for m in messages):
        return {}
    question = _last_user(messages)
    if "计算器" not in question and not re.search(r"\d+\s*[\+\-\*/]\s*\d+", question):
        return {}
    expr = re.search(r"\d[\d\s\.\+\-\*/\(\)]*", question)
    expression = expr.group(0).strip() if expr else "1+1"
    return {
        "id": "call_" + uuid.uuid4().hex[:12],
        "type": "function",
        "function": {"name": "calculator", "arguments": json.dumps({"expression": expression}, ensure_ascii=False)},
    }


def _chat_text(messages: list, tools: list) -> tuple:
    """返回 (content, tool_calls)。tool_calls 非空时 content 为 None。"""
    task = _detect_task(_join(messages))
    prompt = _join(messages)
    question = _last_user(messages)

    if task == "evaluate":
        ctx = _ctx_lines(prompt)
        # 无命中 / 显式要求重试 → 判定资料不足，驱动「改写→再检索」分支
        sufficient = bool(ctx) and "[[NEEDRETRY]]" not in prompt
        reason = "检索到可用片段，资料充分" if sufficient else "未检索到足够相关的片段"
        hint = "" if sufficient else "换用更具体的型号或指标表述再检索"
        return json.dumps({"sufficient": sufficient, "reason": reason, "rewrite_hint": hint}, ensure_ascii=False), []

    if task == "self_check":
        # [[FAILCHECK]] 用于验证「自查不通过 → 重试/收敛」这条分支
        ok = "[[FAILCHECK]]" not in prompt
        reason = "答案均可由参考资料支撑" if ok else "答案存在参考资料未覆盖的内容"
        return json.dumps({"pass": ok, "reason": reason}, ensure_ascii=False), []

    if task == "judge_precision":
        n = max(len(re.findall(r"^\s*\[(\d+)\]", prompt, re.M)), 1)
        scores = [1 if i < max(1, n - 1) else 1 for i in range(n)]
        return json.dumps({"scores": scores}), []

    if task in ("judge_faithfulness", "judge_relevancy"):
        ctx = _ctx_lines(prompt)
        score = 0.9 if ctx or task == "judge_relevancy" else 0.2
        return f"{score}", []

    if task == "multi_query":
        base = re.sub(r"^.*?用户问题：", "", question, flags=re.S).strip() or question
        base = base[:40]
        return "\n".join([
            base,
            f"{base} 的规格参数是多少",
            f"{base} 的常见问题与解决办法",
        ]), []

    if task == "coref":
        cur = re.search(r"当前问题：\s*(.+)$", prompt, re.S)
        return (cur.group(1).strip() if cur else question) or question, []

    if task == "hyde":
        q = re.search(r"问题：\s*(.+)$", prompt, re.S)
        q = (q.group(1).strip() if q else question)[:24]
        return f"关于{q}，设备手册中给出的指标、型号与使用要点如下所述。", []

    tool_calls = _should_call_tool(messages, tools)
    if tool_calls:
        return None, [tool_calls]
    return _compose_answer(messages), []


# ---------------- HTTP 层 ----------------

def _inject_fail(kind: str) -> bool:
    """故障注入：返回 True 表示本次应失败。"""
    with _lock:
        left = _state["fail"].get(kind, 0)
        if left > 0:
            _state["fail"][kind] = left - 1
            _state["errors"][kind] += 1
            return True
        return False


def _count(kind: str):
    with _lock:
        _state["calls"][kind] += 1


class Handler(BaseHTTPRequestHandler):
    server_version = "MockLLM/1.0"
    protocol_version = "HTTP/1.1"

    # ---- 工具方法 ----
    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "POST,GET,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str, etype: str = "server_error"):
        self._send(code, {"error": {"message": message, "type": etype, "code": code}})

    def _sse_start(self):
        """开始 SSE 响应。

        HTTP/1.1 下响应体必须有明确长度或使用分块传输，否则客户端（httpx / openai SDK）
        会一直等待更多数据直到连接关闭——表现为 astream 永久挂起。
        这里显式声明 Transfer-Encoding: chunked，并按分块格式逐帧发送。
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self._chunked = True

    def _write_chunked(self, data: bytes):
        """按 HTTP/1.1 分块编码写出一段数据。"""
        self.wfile.write(f"{len(data):X}\r\n".encode("ascii"))
        self.wfile.write(data)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def _chunked_end(self):
        """结束分块编码（长度 0 的终止块）。"""
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def _sse_chunk(self, obj: dict):
        payload = f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")
        if getattr(self, "_chunked", False):
            self._write_chunked(payload)
        else:
            self.wfile.write(payload)
            self.wfile.flush()

    def log_message(self, fmt, *args):  # 收敛默认访问日志
        pass

    def _log(self, msg: str):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    # ---- 路由 ----
    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/health", "/_health"):
            self._send(200, {"status": "up", "dim": DIM, "topk": TOPK_FEATURES})
        elif path == "/_control":
            with _lock:
                self._send(200, {"code": 0, "data": dict(_state)})
        else:
            self._send_error(404, f"unknown path {path}", "not_found")

    def do_POST(self):
        path = self.path.split("?")[0]
        if path.endswith("/chat/completions"):
            self._handle_chat()
        elif path.endswith("/embeddings"):
            self._handle_embeddings()
        elif "text-rerank" in path:
            self._handle_rerank()
        elif path == "/_control":
            self._handle_control()
        else:
            self._send_error(404, f"unknown path {path}", "not_found")

    def _handle_control(self):
        body = self._read_json()
        with _lock:
            if body.get("reset"):
                _state["fail"] = {}
                _state["calls"] = {"chat": 0, "embedding": 0, "rerank": 0}
                _state["errors"] = {"chat": 0, "embedding": 0, "rerank": 0}
            for k in ("chat", "embedding", "rerank"):
                if k in (body.get("fail") or {}):
                    _state["fail"][k] = int((body["fail"] or {})[k])
            data = dict(_state)
        self._log(f"control -> {json.dumps(data, ensure_ascii=False)}")
        self._send(200, {"code": 0, "data": data})

    # ---- 对话补全 ----
    def _handle_chat(self):
        body = self._read_json()
        _count("chat")
        if LATENCY_MS:
            time.sleep(LATENCY_MS / 1000.0)
        if _inject_fail("chat"):
            self._log("chat <- 注入故障 500")
            self._send_error(500, "mock injected failure: chat")
            return
        messages = body.get("messages") or []
        tools = body.get("tools") or []
        model = body.get("model") or "mock-chat"
        content, tool_calls = _chat_text(messages, tools)
        self._log(f"chat model={model} msgs={len(messages)} tools={len(tools)} "
                  f"task={_detect_task(_join(messages))} toolcall={bool(tool_calls)}")
        if body.get("stream"):
            self._stream_chat(model, content or "", tool_calls)
        else:
            self._send(200, {
                "id": "chatcmpl-" + uuid.uuid4().hex[:20],
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls or None,
                    },
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                }],
                "usage": {"prompt_tokens": 100, "completion_tokens": len(content or "") // 2,
                          "total_tokens": 100 + len(content or "") // 2},
            })

    def _stream_chat(self, model: str, content: str, tool_calls: list):
        cid = "chatcmpl-" + uuid.uuid4().hex[:20]
        created = int(time.time())

        def frame(delta: dict, finish=None):
            return {
                "id": cid, "object": "chat.completion.chunk", "created": created, "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }

        self._sse_start()
        self._sse_chunk(frame({"role": "assistant", "content": ""}))
        if tool_calls:
            # 流式工具调用：按 OpenAI 协议分片返回 arguments
            for tc in tool_calls:
                self._sse_chunk(frame({"tool_calls": [{
                    "index": 0, "id": tc["id"], "type": "function",
                    "function": {"name": tc["function"]["name"], "arguments": ""},
                }]}))
                self._sse_chunk(frame({"tool_calls": [{
                    "index": 0, "function": {"arguments": tc["function"]["arguments"]},
                }]}))
            self._sse_chunk(frame({}, "tool_calls"))
        else:
            step = 3
            for i in range(0, len(content), step):
                self._sse_chunk(frame({"content": content[i:i + step]}))
            self._sse_chunk(frame({}, "stop"))
        if getattr(self, "_chunked", False):
            self._write_chunked(b"data: [DONE]\n\n")
            self._chunked_end()
        else:
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

    # ---- 向量 ----
    def _handle_embeddings(self):
        body = self._read_json()
        _count("embedding")
        if _inject_fail("embedding"):
            self._log("embedding <- 注入故障 500")
            self._send_error(500, "mock injected failure: embedding")
            return
        raw = body.get("input")
        texts = raw if isinstance(raw, list) else ([raw] if isinstance(raw, str) else [])
        dim = int(body.get("dimensions") or DIM)
        data = [{"object": "embedding", "index": i, "embedding": embed(str(t), dim)}
                for i, t in enumerate(texts)]
        self._log(f"embedding n={len(texts)} dim={dim}")
        self._send(200, {
            "object": "list",
            "data": data,
            "model": body.get("model") or "mock-embedding",
            "usage": {"prompt_tokens": 10 * len(texts), "total_tokens": 10 * len(texts)},
        })

    # ---- 重排（DashScope 原生协议） ----
    def _handle_rerank(self):
        body = self._read_json()
        _count("rerank")
        if _inject_fail("rerank"):
            self._log("rerank <- 注入故障 500")
            self._send_error(500, "mock injected failure: rerank")
            return
        inp = body.get("input") or {}
        query = str(inp.get("query") or "")
        docs = inp.get("documents") or []
        top_n = int((body.get("parameters") or {}).get("top_n") or len(docs) or 1)
        qv = embed(query)
        scored = [{"index": i, "relevance_score": round(max(0.0, cosine(qv, embed(str(d)))), 6)}
                  for i, d in enumerate(docs)]
        scored.sort(key=lambda r: r["relevance_score"], reverse=True)
        self._log(f"rerank query={query[:30]!r} docs={len(docs)} top={scored[0]['relevance_score'] if scored else 0}")
        self._send(200, {
            "output": {"results": scored[:top_n]},
            "usage": {"total_tokens": 0},
            "request_id": uuid.uuid4().hex,
        })


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Mock 大模型服务已启动: http://0.0.0.0:{PORT}  (dim={DIM}, topk={TOPK_FEATURES})", flush=True)
    print("  对话: POST /v1/chat/completions", flush=True)
    print("  向量: POST /v1/embeddings", flush=True)
    print("  重排: POST /api/v1/services/rerank/text-rerank/text-rerank", flush=True)
    print("  控制: POST /_control  {\"fail\":{\"chat\":2},\"reset\":true}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

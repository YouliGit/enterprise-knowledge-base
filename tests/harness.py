"""测试基础设施：极简 HTTP 客户端 + 用例登记/汇总（仅用标准库，宿主机可直接跑）。

设计要点：
- 零第三方依赖：用 urllib，避免为了跑测试还要装 requests。
- 用例即数据：每条用例记录 编号/类型/期望/实际/结论/证据，直接可生成测试报告。
- SSE 支持：/chat/ask 是 POST + text/event-stream，EventSource 用不了，这里自己解析。
"""
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

DEFAULT_BASE = "http://127.0.0.1:9090"
DEFAULT_MOCK = "http://127.0.0.1:8898"


class ApiError(Exception):
    pass


class Api:
    """后端 HTTP 客户端。业务异常时后端返回 HTTP 200 + code!=0，这里原样返回 body 供断言。"""

    def __init__(self, base: str = DEFAULT_BASE, token: str | None = None, timeout: int = 120):
        self.base = base.rstrip("/")
        self.token = token
        self.timeout = timeout

    # ---- 基础请求 ----
    def request(self, method: str, path: str, json_body=None, params=None,
                raw_body: bytes | None = None, content_type: str | None = None,
                token: str | None = None, timeout: int | None = None):
        url = self.base + path
        if params:
            from urllib.parse import urlencode
            url += ("&" if "?" in url else "?") + urlencode(params)
        data = raw_body
        headers = {}
        if json_body is not None:
            data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        tok = token if token is not None else self.token
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
                return resp.status, self._parse(body)
        except urllib.error.HTTPError as e:
            return e.code, self._parse(e.read().decode("utf-8", "replace"))
        except Exception as e:
            raise ApiError(f"{method} {path} 请求失败: {type(e).__name__}: {e}")

    @staticmethod
    def _parse(text: str):
        try:
            return json.loads(text)
        except Exception:
            return {"__raw__": text[:2000]}

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, **kw):
        return self.request("POST", path, **kw)

    def put(self, path, **kw):
        return self.request("PUT", path, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)

    # ---- 便捷断言辅助 ----
    def ok_data(self, resp):
        """断言 code==0 并返回 data，失败抛异常，便于用例里直接取值。"""
        status, body = resp
        if not isinstance(body, dict) or body.get("code") != 0:
            raise ApiError(f"期望 code=0，实际 {status} {str(body)[:300]}")
        return body.get("data")

    def login(self, username="admin", password="admin") -> str:
        data = self.ok_data(self.post("/api/login", json_body={"username": username, "password": password}))
        self.token = data["token"]
        return self.token

    # ---- 上传 ----
    def upload(self, kb_id: int, filename: str, content: bytes, token: str | None = None):
        boundary = "----wb" + uuid.uuid4().hex
        parts = []
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"kb_id\"\r\n\r\n{kb_id}\r\n".encode())
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n".encode() + content + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode())
        return self.request("POST", "/api/document/upload", raw_body=b"".join(parts),
                            content_type=f"multipart/form-data; boundary={boundary}", token=token)

    # ---- SSE ----
    def sse(self, path: str, json_body: dict, token: str | None = None, timeout: int = 180) -> list:
        """读取 text/event-stream，返回事件 dict 列表。"""
        url = self.base + path
        req = urllib.request.Request(
            url, data=json.dumps(json_body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "text/event-stream",
                     "Authorization": f"Bearer {token or self.token}"},
            method="POST",
        )
        events = []
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # 必须按「字节流 + 增量解码器」读取：逐字节 decode 会把跨读取边界的
            # 多字节 UTF-8 字符（中文 3 字节）撕裂，配合 errors="ignore" 直接丢字，
            # 表现为中文被吞、只剩 ASCII（如 "# [1][2]"）。用 codecs 增量解码器解决。
            import codecs
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            buf = ""
            while True:
                raw = resp.read(4096)
                if not raw:
                    buf += decoder.decode(b"", final=True)
                    break
                buf += decoder.decode(raw)
                while "\n\n" in buf:
                    chunk, buf = buf.split("\n\n", 1)
                    payload = None
                    for line in chunk.split("\n"):
                        line = line.strip()
                        if line.startswith("data:"):
                            try:
                                payload = json.loads(line[5:].strip())
                            except Exception:
                                payload = None
                    if payload:
                        events.append(payload)
        return events


class Mock:
    """Mock 大模型服务客户端（测试沙箱）。"""

    def __init__(self, base: str = DEFAULT_MOCK):
        self.base = base.rstrip("/")

    def _call(self, path, body=None, method="POST"):
        data = json.dumps(body or {}).encode() if method == "POST" else None
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={"Content-Type": "application/json"}, method=method)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())

    def healthy(self) -> bool:
        try:
            return self._call("/health", method="GET").get("status") == "up"
        except Exception:
            return False

    def inject(self, **kinds):
        """注入故障：inject(chat=2) 表示接下来 2 次对话请求返回 500。"""
        return self._call("/_control", {"fail": kinds})

    def reset(self):
        return self._call("/_control", {"reset": True})

    def state(self):
        return self._call("/_control", method="GET").get("data", {})


class Report:
    """用例登记与汇总；结果同时落 JSON，供测试报告引用原始数据。"""

    def __init__(self, name: str):
        self.name = name
        self.items = []
        self.t0 = time.time()

    def add(self, cid: str, ctype: str, title: str, expected, actual, ok: bool, evidence: str = ""):
        self.items.append({
            "id": cid, "type": ctype, "title": title,
            "expected": str(expected), "actual": str(actual)[:1500],
            "result": "PASS" if ok else "FAIL", "evidence": str(evidence)[:1500],
        })
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {cid} {title} | 期望 {expected} | 实际 {str(actual)[:120]}")

    def case(self, cid: str, ctype: str, title: str, fn):
        """执行一条用例：fn 返回 (ok, expected, actual[, evidence])；异常记为 FAIL。"""
        t = time.time()
        try:
            out = fn()
            if len(out) == 4:
                ok, expected, actual, evidence = out
            else:
                ok, expected, actual = out
                evidence = ""
        except Exception as e:
            ok, expected, actual, evidence = False, "正常执行", f"{type(e).__name__}: {e}", ""
        self.add(cid, ctype, title, expected, actual, ok, f"{evidence} ({int((time.time()-t) * 1000)}ms)")
        return ok

    @property
    def stats(self) -> dict:
        s = {"total": len(self.items), "passed": 0, "failed": 0, "by_type": {}}
        for it in self.items:
            key = "passed" if it["result"] == "PASS" else "failed"
            s[key] += 1
            t = s["by_type"].setdefault(it["type"], {"total": 0, "passed": 0, "failed": 0})
            t["total"] += 1
            t[key] += 1
        s["duration_s"] = round(time.time() - self.t0, 2)
        return s

    def dump(self, path: str | Path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"suite": self.name, "stats": self.stats, "cases": self.items},
                                ensure_ascii=False, indent=2), encoding="utf-8")
        return str(p)

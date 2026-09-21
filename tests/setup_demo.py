"""为人工体验准备一套干净的演示数据（清残留 + 建模型/知识库/文档/策略/应用）。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import Api  # noqa: E402
from suite_e2e import DOCS, QUESTIONS  # noqa: E402

TS = str(int(time.time()))
api = Api()
api.login()
print("登录 OK")

# ---------- 1. 清理诊断残留 ----------
# 删掉所有诊断产生的知识库 / 应用 / 模型（名字带「诊断」「SG2」「冒烟」「测试」前缀）
def purge():
    n = 0
    # 应用
    for x in api.ok_data(api.get("/api/chatApp/page", params={"page": 1, "page_size": 200}))["list"]:
        if any(k in x["name"] for k in ("诊断", "SG2App", "冒烟", "测试问答应用")):
            api.delete(f"/api/chatApp/{x['id']}"); n += 1
    # 知识库
    for x in api.ok_data(api.get("/api/knowledgeBase/page", params={"page": 1, "page_size": 200}))["list"]:
        if any(k in x["name"] for k in ("诊断", "SG2KB", "TOKKB", "D63KB", "D91KB", "测试知识库")):
            api.delete(f"/api/knowledgeBase/{x['id']}"); n += 1
    # 模型配置
    for x in api.ok_data(api.get("/api/aiModel/page", params={"page": 1, "page_size": 200}))["list"]:
        if any(k in x["name"] for k in ("诊断", "流式诊断", "沙箱-", "测试向量模型", "测试对话模型", "测试重排模型")):
            api.delete(f"/api/aiModel/{x['id']}"); n += 1
    return n


print("清理残留 %d 项" % purge())

# ---------- 2. 建三类模型（全部指向沙箱） ----------
MOCK_OPENAI = "http://mock-llm:8000/v1"     # OpenAI 兼容（对话 / 向量）
MOCK_NATIVE = "http://mock-llm:8000"        # DashScope 原生（重排）

mk = {}
for typ, name, model, base in (
    ("chat", "演示-对话模型(沙箱)", "mock-qwen-plus", MOCK_OPENAI),
    ("embedding", "演示-向量模型(沙箱)", "mock-embedding-v4", MOCK_OPENAI),
    ("rerank", "演示-重排模型(沙箱)", "mock-gte-rerank-v2", MOCK_NATIVE),
):
    mk[typ] = api.ok_data(api.post("/api/aiModel", json_body={
        "name": name, "type": typ, "model": model, "api_base": base,
        "api_key": "sk-sandbox", "enabled": 1, "dimension": 1024}))["id"]
print("模型配置:", mk)

# 连通性自检
for typ in ("chat", "embedding", "rerank"):
    r = api.post(f"/api/aiModel/{mk[typ]}/test")
    print("  连通测试 %-9s -> code=%s ok=%s" % (typ, r[1].get("code"), (r[1].get("data") or {}).get("ok")))

# ---------- 3. 建知识库 + 传 3 份文档 ----------
kb = api.ok_data(api.post("/api/knowledgeBase", json_body={
    "name": "演示知识库(企业制度与产品)",
    "description": "光模块产品手册 / 员工考勤制度 / 费用报销办法",
    "vector_model_id": mk["embedding"]}))["id"]
print("知识库 id=%s" % kb)

doc_ids = {}
for name, text in DOCS.items():
    r = api.upload(kb, name, text.encode("utf-8"))
    doc_ids[name] = r[1]["data"]["id"]

# 等入库
t0 = time.time()
while time.time() - t0 < 120:
    page = api.ok_data(api.get("/api/document/page", params={"kb_id": kb, "page": 1, "page_size": 50}))
    done = [r for r in page["list"] if r["id"] in doc_ids.values() and r["status"] in ("parsed", "failed")]
    if len(done) == len(doc_ids):
        break
    time.sleep(1)
print("入库结果:", {r["name"]: (r["status"], r["chunk_count"]) for r in page["list"] if r["id"] in doc_ids.values()})

reb = api.ok_data(api.get(f"/api/knowledgeBase/{kb}/rebuild_status"))
print("向量数=%s 片段数=%s" % (reb["vector_count"], reb["chunk_count"]))

# ---------- 4. 建检索策略（阈值适配沙箱） ----------
strat = api.ok_data(api.post("/api/retrievalStrategy", json_body={
    "name": "演示-混合检索(宽松阈值)", "rewrite_mode": "multi_query",
    "cosine_threshold": 0.10, "rerank_threshold": 0.02}))["id"]
print("检索策略 id=%s" % strat)

# ---------- 5. 建两个问答应用 ----------
app_plain = api.ok_data(api.post("/api/chatApp", json_body={
    "name": "演示应用-普通问答", "description": "混合检索 + 流式问答",
    "model_config_id": mk["chat"], "retrieval_strategy_id": strat,
    "max_history": 3, "show_ref": 1, "use_agent": 0}))["id"]
api.put(f"/api/chatApp/{app_plain}/kbs", json_body={"kb_ids": [kb]})

app_agent = api.ok_data(api.post("/api/chatApp", json_body={
    "name": "演示应用-Agentic RAG", "description": "LangGraph 状态图 + 工具调用",
    "model_config_id": mk["chat"], "retrieval_strategy_id": strat,
    "max_history": 3, "show_ref": 1, "use_agent": 1}))["id"]
api.put(f"/api/chatApp/{app_agent}/kbs", json_body={"kb_ids": [kb]})

# ---------- 6. 冒烟自检：跑一遍问答 ----------
sid = api.ok_data(api.post("/api/chat/session", json_body={"app_id": app_plain, "title": "冒烟"}))["id"]
q = QUESTIONS["光模块产品手册.md"]
ev = api.sse("/api/chat/ask", {"session_id": sid, "query": q})
ans = "".join((e.get("delta") or "") for e in ev if e.get("type") == "token")
print("\n冒烟问答: 事件=%s" % [e.get("type") for e in ev])
print("  答案=%r" % ans[:80])
api.delete(f"/api/chat/session/{sid}")

# 清掉这 2 个诊断会话
for s in api.ok_data(api.get("/api/chat/session/page", params={"page": 1, "page_size": 50}))["list"]:
    api.delete(f"/api/chat/session/{s['id']}")

print("""
============================================================
 演示数据就绪
============================================================
 管理端地址 : http://localhost:8080    （admin / admin）
 后端接口   : http://localhost:9090/docs  （Swagger）
 沙箱大模型 : http://127.0.0.1:8898/health

 模型配置 : chat=%s embedding=%s rerank=%s
 知识库   : %s  演示知识库(企业制度与产品)   [3 份文档已入库]
 策略     : %s  演示-混合检索(宽松阈值)
 应用     : %s  演示应用-普通问答
            %s  演示应用-Agentic RAG
============================================================
""" % (mk["chat"], mk["embedding"], mk["rerank"], kb, strat, app_plain, app_agent))

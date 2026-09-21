"""全链路端到端测试套件（依赖 Mock 大模型沙箱）。

链路：模型配置 → 连通性 → Prompt/工具 → 知识库 → 文档入库(解析→切分→向量化)
      → 片段管理 → 混合检索(StageTrace/量纲) → 召回对比 → 问答应用 → SSE 流式问答
      → Agentic RAG(状态图/时间线) → LLM-as-judge 评测 → 策略对比 → 反馈闭环

运行前需先起沙箱：
    docker compose --profile test up -d --build
运行：python suite_e2e.py      （结果落 results/e2e_results.json）
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Api, Mock, Report  # noqa: E402

R = Report("全链路端到端测试")
MOCK_BASE = "http://mock-llm:8000"          # 后端在 Docker 网络内访问 Mock 的地址
MOCK_OPENAI = MOCK_BASE + "/v1"

DOCS = {
    "光模块产品手册.md": (
        "# 光模块产品手册\n\n"
        "## 1. 产品概述\n"
        "本手册适用于 GTE-3000 系列光模块，用于数据中心内部与数据中心之间的高速互联。"
        "该系列产品支持 10Gbps 与 25Gbps 两种速率档位，采用可热插拔的 SFP+ 封装，"
        "广泛应用于服务器网卡、交换机上行端口与存储网络。\n\n"
        "## 2. 工作温度范围\n"
        "光模块的工作温度范围是选型时最重要的环境指标。GTE-3000 系列提供两种温度等级：\n"
        "工业级光模块的工作温度范围为 -40℃ 到 85℃，存储温度范围为 -40℃ 到 85℃；\n"
        "商业级光模块的工作温度范围为 0℃ 到 70℃，存储温度范围为 -40℃ 到 85℃。\n"
        "当环境温度超出工作温度范围时，光模块会出现光功率漂移、误码率上升甚至链路中断，"
        "因此户外机柜、边缘接入与工业现场应选用工业级模块。\n\n"
        "## 3. 关键参数\n"
        "发射光功率范围为 -8.2dBm 到 0.5dBm，接收灵敏度优于 -14.4dBm，消光比大于 3.5dB。"
        "典型功耗为 1.2W，最大功耗 1.5W。接口类型为 LC 双工。\n\n"
        "## 4. 故障排查\n"
        "光功率过低的常见原因包括光接口污染、光纤弯折半径不足、模块老化。"
        "建议排查顺序为：先用专用清洁笔清洁光接口，再用光功率计测量收发光功率，"
        "最后更换模块进行交叉验证。若清洁后仍不达标，请联系售后更换。\n"
    ),
    "员工考勤与假期制度.md": (
        "# 员工考勤与假期管理制度\n\n"
        "## 1. 工作时间与打卡\n"
        "公司实行标准工时制，工作时间为每日 9:00 至 18:00，午休 12:00 至 13:00。"
        "员工每日上下班均需在考勤系统中打卡。迟到超过 30 分钟计为旷工半天，"
        "一个月内累计迟到 3 次以上将影响当月绩效。\n\n"
        "## 2. 年假\n"
        "员工入职满一年享有 5 天带薪年假，满三年享有 10 天，满五年及以上享有 15 天。"
        "年假需提前三个工作日在系统中提交申请，由直属主管审批通过后方可休假。"
        "当年未休完的年假最多可结转 5 天至次年第一季度，逾期作废。\n\n"
        "## 3. 病假与事假\n"
        "病假需提供二级以上医院出具的病假证明，病假期间按基本工资的 80% 计发。"
        "事假为无薪假，全年累计不得超过 15 天。\n\n"
        "## 4. 加班与调休\n"
        "因工作需要加班的，需提前提交加班申请。工作日加班可申请调休或加班费，"
        "休息日加班优先安排调休，法定节假日加班按国家规定支付三倍工资。\n"
    ),
    "费用报销管理办法.md": (
        "# 费用报销管理办法\n\n"
        "## 1. 报销时限\n"
        "差旅费需在出差结束后的十个工作日内提交报销申请，超过时限的原则上不予受理。"
        "其他费用应在费用发生当月提交，跨年度费用一律不予报销。\n\n"
        "## 2. 报销流程\n"
        "报销流程分为四个环节：填写报销单、直属主管审批、财务审核、银行打款。"
        "材料齐全的情况下，整个流程一般需要五个工作日完成。"
        "单笔金额超过 5000 元的费用，需分管领导额外签批。\n\n"
        "## 3. 差旅标准\n"
        "交通费按照职级对应标准执行，原则上选择经济舱与经济座。"
        "住宿费按城市等级分档：一线城市每晚上限 600 元，二线城市每晚上限 450 元，"
        "其他城市每晚上限 350 元。伙食补助每人每天 100 元。\n\n"
        "## 4. 发票要求\n"
        "报销必须提供发票原件与行程单。发票抬头须为公司全称，"
        "发票内容应与实际发生费用一致。虚报费用的，按公司制度严肃处理。\n"
    ),
}

QUESTIONS = {
    "光模块产品手册.md": "光模块的工作温度范围是多少",
    "员工考勤与假期制度.md": "年假有多少天，需要提前几天申请",
    "费用报销管理办法.md": "报销流程需要几个工作日，超过5000元怎么办",
}


def main() -> int:
    api = Api()
    api.login()
    mock = Mock()
    ts = int(time.time())
    created = {"kb": None, "docs": [], "app": None, "sessions": [], "models": [], "dataset": None,
               "strategies": [], "run": None, "cmp": None}

    if not mock.healthy():
        print("!! Mock 大模型服务不可达，请先执行 docker compose --profile test up -d 后重试")
        return 2
    mock.reset()
    print(f"Mock 沙箱就绪：{mock.state()}")

    # ---------------- 1. 模型配置 ----------------
    print("\n== 1 模型配置与连通性 ==")
    mk = {}
    for typ, name, model, base in (
        ("chat", "沙箱-对话模型", "mock-qwen-plus", MOCK_OPENAI),
        ("embedding", "沙箱-向量模型", "mock-embedding-v4", MOCK_OPENAI),
        ("rerank", "沙箱-重排模型", "mock-gte-rerank-v2", MOCK_BASE),
    ):
        r = api.post("/api/aiModel", json_body={"name": f"{name}_{ts}", "type": typ, "model": model,
                                                "api_base": base, "api_key": "sk-sandbox", "dimension": 1024})
        mk[typ] = api.ok_data(r)["id"]
        created["models"].append(mk[typ])
    R.case("E2E-1.1", "功能", "创建三类模型配置(chat/embedding/rerank)", lambda: (
        len(mk) == 3 and all(isinstance(v, int) for v in mk.values()), "3 个配置创建成功", str(mk)))

    def conn_all():
        res = {}
        for typ in ("chat", "embedding", "rerank"):
            r = api.post(f"/api/aiModel/{mk[typ]}/test")
            res[typ] = (r[1].get("code") == 0 and r[1]["data"].get("ok") is True)
        return (all(res.values()), "三类模型连通性测试全部 ok=true",
                str({k: ("ok" if v else "fail") for k, v in res.items()}))

    R.case("E2E-1.2", "功能", "三类模型连通性测试通过", conn_all)

    # ---------------- 2. Prompt / 工具 ----------------
    print("\n== 2 Prompt 与工具中心 ==")
    api.post("/api/prompt/import_builtin")
    api.post("/api/tool/import_builtin")
    R.case("E2E-2.1", "功能", "内置 Prompt 模板齐备(11 个)", lambda: (
        (lambda r: (r[1].get("code") == 0 and r[1]["data"]["total"] >= 11, "total>=11",
                    f"total={r[1]['data'].get('total')}"))(api.get("/api/prompt/page", params={"page": 1, "page_size": 50}))))
    R.case("E2E-2.2", "功能", "内置工具齐备(3 个)", lambda: (
        (lambda r: (r[1].get("code") == 0 and r[1]["data"]["total"] >= 3, "total>=3",
                    f"total={r[1]['data'].get('total')}"))(api.get("/api/tool/page", params={"page": 1, "page_size": 50}))))

    # ---------------- 3. 知识库 ----------------
    print("\n== 3 知识库与文档入库 ==")
    kb = api.post("/api/knowledgeBase", json_body={"name": f"沙箱知识库_{ts}", "description": "端到端测试",
                                                   "vector_model_id": mk["embedding"]})
    kb_id = api.ok_data(kb)["id"]
    created["kb"] = kb_id

    doc_ids = {}
    for fname, content in DOCS.items():
        r = api.upload(kb_id, fname, content.encode("utf-8"))
        if r[1].get("code") == 0:
            doc_ids[fname] = r[1]["data"]["id"]
            created["docs"].append(r[1]["data"]["id"])
    R.case("E2E-3.1", "功能", "上传 3 份知识文档", lambda: (
        len(doc_ids) == 3, "3 份均上传成功", str(doc_ids)))

    settled = {}
    t0 = time.time()
    while time.time() - t0 < 120 and len(settled) < len(doc_ids):
        _, page = api.get("/api/document/page", params={"kb_id": kb_id, "page": 1, "page_size": 50})
        for row in page["data"]["list"]:
            if row["id"] in doc_ids.values() and row["status"] in ("parsed", "failed"):
                settled[row["id"]] = row
        if len(settled) < len(doc_ids):
            time.sleep(2)

    R.case("E2E-3.2", "功能", "全部文档解析完成(后台任务不丢)", lambda: (
        len(settled) == len(doc_ids) and all(r["status"] == "parsed" for r in settled.values()),
        f"{len(doc_ids)} 份均 status=parsed",
        str({k: (v["status"], v["chunk_count"], v["error"][:40]) for k, v in settled.items()})))
    R.case("E2E-3.3", "功能", "切分产生片段且每个文档都有片段", lambda: (
        all(r["chunk_count"] > 0 for r in settled.values()), "chunk_count 全部 >0",
        str({k: v["chunk_count"] for k, v in settled.items()})))

    def vector_ok():
        _, r = api.get(f"/api/knowledgeBase/{kb_id}/rebuild_status")
        vc, cc = int(r["data"]["vector_count"]), r["data"]["chunk_count"]
        return (vc > 0 and vc == cc, "向量数>0 且与启用子块数一致", f"vector={vc} chunk={cc}")

    R.case("E2E-3.4", "功能", "子块全部完成向量化入库(PGVector)", vector_ok)

    # ---------------- 4. 片段管理 ----------------
    print("\n== 4 片段管理 ==")
    _, cp = api.get("/api/chunk/page", params={"kb_id": kb_id, "page": 1, "page_size": 200, "only_child": 0})
    all_chunks = cp["data"]["list"]
    parents = {d: [c for c in all_chunks if c["is_parent"] == 1 and c["doc_id"] == i] for d, i in doc_ids.items()}
    children = [c for c in all_chunks if c["is_parent"] == 0]
    R.case("E2E-4.1", "功能", "父子分块结构正确(父块/子块均入库且子块挂在父块下)", lambda: (
        all(parents.values()) and all(c["parent_id"] for c in children),
        "每个文档均有父块，且所有子块 parent_id 非空",
        f"父块数={sum(len(v) for v in parents.values())} 子块数={len(children)}"))

    def chunk_fix():
        c = children[0]
        new_text = c["content"] + "\n（人工补充：本条为自动化测试修正内容。）"
        u = api.put(f"/api/chunk/{c['id']}", json_body={"content": new_text})
        _, d = api.get(f"/api/chunk/{c['id']}")
        return (u[1].get("code") == 0 and d["data"]["content"] == new_text and d["data"]["char_len"] == len(new_text),
                "code=0 且内容与长度已更新", f"len={d['data']['char_len']}")

    R.case("E2E-4.2", "功能", "片段人工修正后重新向量化", chunk_fix)

    def chunk_disable():
        c = children[1]
        api.put(f"/api/chunk/{c['id']}/status", json_body={"enabled": 0})
        _, r = api.get(f"/api/knowledgeBase/{kb_id}/rebuild_status")
        vc_off = int(r["data"]["vector_count"])
        api.put(f"/api/chunk/{c['id']}/status", json_body={"enabled": 1})
        _, r2 = api.get(f"/api/knowledgeBase/{kb_id}/rebuild_status")
        vc_on = int(r2["data"]["vector_count"])
        return (vc_off < vc_on and vc_on == len(children), "停用后向量减少，启用后恢复",
                f"停用={vc_off} 启用={vc_on} 子块总数={len(children)}")

    R.case("E2E-4.3", "功能", "片段停用/启用与向量同步", chunk_disable)

    # ---------------- 5. 检索与量纲追踪 ----------------
    print("\n== 5 混合检索与量纲追踪 ==")
    def strategy(name, **kw):
        body = {"name": f"{name}_{ts}"}
        body.update(kw)
        r = api.post("/api/retrievalStrategy", json_body=body)
        sid = api.ok_data(r)["id"]
        created["strategies"].append(sid)
        return sid

    s_default = strategy("沙箱-默认阈值混合", rewrite_mode="multi_query")
    s_loose = strategy("沙箱-宽松阈值混合", cosine_threshold=0.10, rerank_threshold=0.02)
    s_vec = strategy("沙箱-纯向量基线", bm25_top_k=0, use_rewrite=0, rerank_enabled=0)

    def trace_check():
        q = QUESTIONS["光模块产品手册.md"]
        _, r = api.post("/api/retrieval/test", json_body={"kb_id": kb_id, "query": q, "strategy_id": s_loose})
        if r.get("code") != 0:
            return (False, "code=0", str(r.get("msg"))[:150])
        data = r["data"]
        stages = [t["stage"] for t in data["traces"]]
        scales = {t["stage"]: (t["scale"], t["threshold_applies"]) for t in data["traces"]}
        ok = all(s in stages for s in ("rewrite", "vector", "bm25", "rrf", "backfill", "rerank"))
        ok = ok and scales.get("bm25", (None, None))[1] is False and scales.get("rrf", (None, None))[1] is False
        ok = ok and scales.get("vector", (None, None))[1] is True
        return (ok, "阶段齐备且量纲阈值适用性标注正确",
                f"stages={stages} scales={scales}")

    R.case("E2E-5.1", "功能", "检索返回完整 StageTrace 且量纲标注正确", trace_check)

    def recall_correct():
        q = QUESTIONS["光模块产品手册.md"]
        _, r = api.post("/api/retrieval/test", json_body={"kb_id": kb_id, "query": q, "strategy_id": s_loose})
        ctx = r["data"]["contexts"]
        if not ctx:
            return (False, "至少召回 1 个父块", "0 命中")
        top = ctx[0]
        ok = "光模块" in top["content"] and ("温度" in top["content"])
        return (ok, "Top1 命中光模块手册中讲温度范围的父块",
                f"top1 chunk={top['chunk_id']} 预览={top['content'][:60]!r} 分数={top['scores']}")

    R.case("E2E-5.2", "功能", "检索命中正确来源文档(Top1 正确)", recall_correct)

    def bm25_rescue():
        """默认阈值 0.30 下，向量通道可能被过滤，BM25 通道应兜底召回（量纲设计的关键验证）"""
        q = QUESTIONS["员工考勤与假期制度.md"]
        _, r = api.post("/api/retrieval/test", json_body={"kb_id": kb_id, "query": q, "strategy_id": s_default})
        if r.get("code") != 0:
            return (False, "code=0", str(r.get("msg"))[:150])
        ctx = r["data"]["contexts"]
        vec_trace = next(t for t in r["data"]["traces"] if t["stage"] == "vector")
        bm25_trace = next(t for t in r["data"]["traces"] if t["stage"] == "bm25")
        ok = len(ctx) > 0 and len(bm25_trace["hits"]) > 0
        return (ok, "严格阈值下仍有召回（BM25/RRF 兜底生效）",
                f"向量命中={len(vec_trace['hits'])} BM25命中={len(bm25_trace['hits'])} 最终上下文={len(ctx)}")

    R.case("E2E-5.3", "功能", "严格阈值下 BM25 通道兜底召回", bm25_rescue)

    def compare_arms():
        q = QUESTIONS["费用报销管理办法.md"]
        r = api.post("/api/retrieval/compare", json_body={"kb_id": kb_id, "query": q, "strategy_ids": [s_loose, s_vec]})
        arms = r[1]["data"]["arms"]
        ok = len(arms) == 2 and all("traces" in a for a in arms)
        return (ok, "2 套策略并排返回且各自带 StageTrace",
                f"arms={[len(a.get('contexts', [])) for a in arms]} cost={[a.get('cost_ms') for a in arms]}")

    R.case("E2E-5.4", "功能", "召回调试台 2 套策略并排对比", compare_arms)

    # ---------------- 6. 问答应用 + SSE ----------------
    print("\n== 6 问答应用与 SSE 流式问答 ==")
    app = api.post("/api/chatApp", json_body={"name": f"沙箱问答应用_{ts}", "description": "端到端",
                                              "model_config_id": mk["chat"], "retrieval_strategy_id": s_loose,
                                              "max_history": 3, "show_ref": 1, "use_agent": 0})
    app_id = api.ok_data(app)["id"]
    created["app"] = app_id
    api.put(f"/api/chatApp/{app_id}/kbs", json_body={"kb_ids": [kb_id]})
    R.case("E2E-6.1", "功能", "创建问答应用并绑定知识库/模型/策略", lambda: (
        app_id is not None, "code=0", f"app_id={app_id}"))

    def sse_ask():
        s = api.post("/api/chat/session", json_body={"app_id": app_id, "title": "SSE 用例"})
        sid = api.ok_data(s)["id"]
        created["sessions"].append(sid)
        q = QUESTIONS["光模块产品手册.md"]
        ev = api.sse("/api/chat/ask", {"session_id": sid, "query": q})
        types = [e.get("type") for e in ev]
        answer = "".join((e.get("delta") or "") for e in ev if e.get("type") == "token")
        refs = next((e.get("refs") for e in ev if e.get("type") == "refs"), [])
        done = next((e for e in ev if e.get("type") == "done"), None)
        ok = (types[:2] == ["start", "token"] or "start" in types) and "done" in types and bool(answer.strip())
        ok = ok and bool(refs) and not any(t == "error" for t in types)
        return (ok, "事件序列 start→token…→refs→done，答案非空且有引用",
                f"事件类型={types[:4]}…{types[-3:]} 答案长度={len(answer)} 引用数={len(refs)} done={bool(done)}")

    R.case("E2E-6.2", "功能", "SSE 流式问答完整事件序列", sse_ask)

    def answer_grounded():
        s = api.post("/api/chat/session", json_body={"app_id": app_id, "title": "答案质量用例"})
        sid = api.ok_data(s)["id"]
        created["sessions"].append(sid)
        q = QUESTIONS["光模块产品手册.md"]
        ev = api.sse("/api/chat/ask", {"session_id": sid, "query": q})
        answer = "".join((e.get("delta") or "") for e in ev if e.get("type") == "token")
        _, h = api.get(f"/api/chat/history/{sid}")
        rows = h["data"]
        ok = len(rows) == 2 and rows[0]["role"] == "user" and rows[1]["role"] == "assistant"
        ok = ok and rows[1]["content"] == answer and len(rows[1]["refs_json"]) > 10
        return (ok, "会话落库 user+assistant 两条且答案与引用入库",
                f"消息数={len(rows)} 角色={[r['role'] for r in rows]} 引用长度={len(rows[1]['refs_json']) if len(rows)>1 else 0}")

    R.case("E2E-6.3", "功能", "问答过程与会话落库一致", answer_grounded)

    def multi_turn():
        s = api.post("/api/chat/session", json_body={"app_id": app_id, "title": "多轮用例"})
        sid = api.ok_data(s)["id"]
        created["sessions"].append(sid)
        api.sse("/api/chat/ask", {"session_id": sid, "query": QUESTIONS["光模块产品手册.md"]})
        ev = api.sse("/api/chat/ask", {"session_id": sid, "query": "那它的存储温度呢"})
        answer = "".join((e.get("delta") or "") for e in ev if e.get("type") == "token")
        _, h = api.get(f"/api/chat/history/{sid}")
        return (len(h["data"]) == 4 and bool(answer.strip()), "4 条消息且第二轮有答案",
                f"消息数={len(h['data'])} 第二轮答案长度={len(answer)}")

    R.case("E2E-6.4", "功能", "多轮对话历史携带正常", multi_turn)

    def feedback_loop():
        _, h = api.get(f"/api/chat/history/{created['sessions'][0]}")
        aid = [m for m in h["data"] if m["role"] == "assistant"][0]["id"]
        f = api.post("/api/chat/feedback", json_body={"message_id": aid, "feedback": "useless"})
        _, dash = api.get("/api/dashboard/summary")
        cnt = dash["data"]["optimize"]
        api.post("/api/chat/feedback", json_body={"message_id": aid, "feedback": ""})
        return (f[1].get("code") == 0 and cnt >= 1, "反馈成功且计入首页待优化数",
                f"待优化数={cnt}")

    R.case("E2E-6.5", "功能", "点踩反馈进入首页待优化统计", feedback_loop)

    # ---------------- 7. Agentic RAG ----------------
    print("\n== 7 Agentic RAG（状态图与时间线） ==")
    agent_app = api.post("/api/chatApp", json_body={"name": f"沙箱Agent应用_{ts}", "model_config_id": mk["chat"],
                                                    "retrieval_strategy_id": s_loose, "use_agent": 1,
                                                    "max_history": 3, "show_ref": 1})
    agent_app_id = api.ok_data(agent_app)["id"]
    api.put(f"/api/chatApp/{agent_app_id}/kbs", json_body={"kb_ids": [kb_id]})

    def agent_run_sync():
        q = QUESTIONS["光模块产品手册.md"]
        r = api.post("/api/agent/run", json_body={"app_id": agent_app_id, "query": q})
        if r[1].get("code") != 0:
            return (False, "code=0", str(r[1].get("msg"))[:200])
        d = r[1]["data"]
        return (bool(d.get("answer")) and d.get("rounds", 0) >= 1, "返回答案且轮次>=1",
                f"rounds={d.get('rounds')} 上下文={len(d.get('contexts', []))} 答案={str(d.get('answer'))[:60]!r}")

    R.case("E2E-7.1", "功能", "Agent 调试接口同步执行成功", agent_run_sync)

    def agent_steps():
        r = api.post("/api/agent/run", json_body={"app_id": agent_app_id, "query": QUESTIONS["费用报销管理办法.md"]})
        if r[1].get("code") != 0:
            return (False, "code=0", str(r[1].get("msg"))[:200])
        run_id = r[1]["data"]["run_id"]
        _, s = api.get(f"/api/agent/steps/{run_id}")
        steps = s["data"]
        nodes = [x["node"] for x in steps]
        seqs = [x["seq"] for x in steps]
        ok_nodes = all(n in nodes for n in ("retrieve", "evaluate", "generate", "self_check"))
        ok_seq = seqs == list(range(1, len(seqs) + 1))
        return (ok_nodes and ok_seq, "节点齐备且 seq 从 1 递增不重复",
                f"nodes={nodes} seq={seqs}")

    R.case("E2E-7.2", "功能", "Agent 时间线步骤完整且 seq 唯一递增", agent_steps)

    def self_check_real():
        """自查节点必须真正调用模型，而不是被 except 吞掉走「异常默认通过」"""
        r = api.post("/api/agent/run", json_body={"app_id": agent_app_id, "query": QUESTIONS["员工考勤与假期制度.md"]})
        run_id = r[1]["data"]["run_id"]
        _, s = api.get(f"/api/agent/steps/{run_id}")
        sc = [x for x in s["data"] if x["node"] == "self_check"]
        if not sc:
            return (False, "存在 self_check 步骤", "无自查步骤")
        thought = sc[0]["thought"] or ""
        ok = "自查异常" not in thought and "get_chat_model" not in thought
        return (ok, "自查节点正常调用裁判模型（thought 不含异常降级信息）",
                f"thought={thought[:120]!r} input={sc[0]['input_json'][:80]}")

    R.case("E2E-7.3", "功能", "Agent 自查节点真实执行(未静默降级)", self_check_real)

    def agent_sse():
        s = api.post("/api/chat/session", json_body={"app_id": agent_app_id, "title": "Agent SSE 用例"})
        sid = api.ok_data(s)["id"]
        created["sessions"].append(sid)
        ev = api.sse("/api/chat/ask", {"session_id": sid, "query": QUESTIONS["光模块产品手册.md"]})
        types = [e.get("type") for e in ev]
        steps = [e["data"]["node"] for e in ev if e.get("type") == "step"]
        answer = "".join((e.get("delta") or "") for e in ev if e.get("type") == "token")
        ok = "agent_start" in types and "step" in types and "done" in types and bool(answer.strip())
        return (ok, "含 agent_start/step/done 事件且步奏实时推送",
                f"事件={types} 步骤节点={steps} 答案长度={len(answer)}")

    R.case("E2E-7.4", "功能", "Agent 模式 SSE 实时推送步骤与答案", agent_sse)

    def agent_record():
        _, p = api.get("/api/agent/runPage", params={"page": 1, "page_size": 20})
        rows = [x for x in p["data"]["list"] if x["app_id"] == agent_app_id]
        ok = bool(rows) and all(x["status"] == "done" for x in rows)
        ok = ok and any(x["final_answer"] and x["total_cost_ms"] >= 0 for x in rows)
        return (ok, "运行记录状态均为 done 且有答案与耗时",
                f"记录数={len(rows)} 状态={[x['status'] for x in rows]}")

    R.case("E2E-7.5", "功能", "Agent 运行记录落库完整", agent_record)

    def tool_loop():
        """Function Calling 工具循环：问一个需要计算的算术题"""
        s = api.post("/api/chat/session", json_body={"app_id": agent_app_id, "title": "工具用例"})
        sid = api.ok_data(s)["id"]
        created["sessions"].append(sid)
        ev = api.sse("/api/chat/ask", {"session_id": sid, "query": "帮我用计算器计算 123*(45+67) 等于多少"})
        types = [e.get("type") for e in ev]
        answer = "".join((e.get("delta") or "") for e in ev if e.get("type") == "token")
        _, lg = api.get("/api/tool/log/page", params={"query": "calculator", "page": 1, "page_size": 10})
        ok = "done" in types and bool(answer.strip()) and int(lg["data"]["total"]) >= 1
        return (ok, "工具被调用并落日志，最终答案非空",
                f"工具日志数={lg['data']['total']} 答案={answer[:60]!r} 事件={types[:6]}")

    R.case("E2E-7.6", "功能", "Function Calling 工具调用闭环", tool_loop)

    # ---------------- 8. 评测 ----------------
    print("\n== 8 LLM-as-judge 评测与策略对比 ==")
    ds = api.post("/api/eval/dataset", json_body={"name": f"沙箱评测集_{ts}", "kb_id": kb_id})
    ds_id = api.ok_data(ds)["id"]
    created["dataset"] = ds_id

    def expected_ids_for(doc_name, keyword):
        rows = [c for c in all_chunks if c["is_parent"] == 1 and c["doc_id"] == doc_ids[doc_name] and keyword in c["content"]]
        return [c["id"] for c in rows] or [c["id"] for c in all_chunks if c["is_parent"] == 1 and c["doc_id"] == doc_ids[doc_name]][:1]

    cases = []
    for doc_name, q in QUESTIONS.items():
        kw = {"光模块产品手册.md": "温度", "员工考勤与假期制度.md": "年假", "费用报销管理办法.md": "报销流程"}[doc_name]
        cases.append({"question": q, "ground_truth": f"依据《{doc_name}》回答", "source_chunk_ids": expected_ids_for(doc_name, kw)})
    R.case("E2E-8.1", "功能", "评测用例导入(含来源片段ID)", lambda: (
        (lambda r: (r[1].get("code") == 0 and r[1]["data"]["created"] == 3, "created=3",
                    f"{r[1].get('data')}"))(api.post("/api/eval/case/batch", params={"dataset_id": ds_id}, json_body={"cases": cases}))))

    run = api.post("/api/eval/run", json_body={"dataset_id": ds_id, "kb_id": kb_id, "strategy_id": s_loose,
                                               "report_name": f"沙箱评测_{ts}"})
    run_id = api.ok_data(run)["id"]
    created["run"] = run_id

    def wait_run(rid, timeout=180):
        t0 = time.time()
        while time.time() - t0 < timeout:
            _, p = api.get("/api/eval/run/page", params={"page": 1, "page_size": 20})
            row = next((x for x in p["data"]["list"] if x["id"] == rid), None)
            if row and row["status"] in ("done", "failed"):
                return row
            time.sleep(2)
        return None

    def eval_done():
        row = wait_run(run_id)
        if not row:
            return (False, "评测在 180s 内完成", "超时未结束")
        ok = row["status"] == "done" and row["case_count"] == 3
        ok = ok and row["recall"] >= 0 and row["faithfulness"] > 0 and row["relevancy"] > 0
        return (ok, "status=done，用例=3，四指标均已计算",
                f"status={row['status']} recall={row['recall']} precision={row['precision']} "
                f"faith={row['faithfulness']} relev={row['relevancy']} overall={row['overall']} err={row['error'][:60]}")

    R.case("E2E-8.2", "功能", "批量评测完成且四指标产出", eval_done)

    def eval_items():
        _, r = api.get(f"/api/eval/run/{run_id}/items")
        items = r["data"]
        ok = len(items) == 3 and all(i["answer"] for i in items)
        recall_worked = any(i["recall"] > 0 for i in items)
        return (ok and recall_worked, "3 条明细均有答案，且 Context Recall 基于片段ID运算生效",
                f"明细={[(i['question'][:8], i['recall'], round(i['overall'],3)) for i in items]}")

    R.case("E2E-8.3", "功能", "评测明细与 Context Recall 运算正确", eval_items)

    cmp_run = api.post("/api/eval/compare", json_body={"name": f"沙箱对比_{ts}", "kb_id": kb_id, "dataset_id": ds_id,
                                                       "strategy_ids": [s_loose, s_vec]})
    cmp_id = api.ok_data(cmp_run)["id"]
    created["cmp"] = cmp_id

    def compare_done():
        t0 = time.time()
        row = None
        while time.time() - t0 < 240:
            _, p = api.get("/api/eval/compare/page", params={"page": 1, "page_size": 20})
            row = next((x for x in p["data"]["list"] if x["id"] == cmp_id), None)
            if row and row["status"] in ("done", "failed"):
                break
            time.sleep(2)
        if not row:
            return (False, "对比在 240s 内完成", "超时")
        arms = row.get("arms") or []
        ok = row["status"] == "done" and len(arms) == 2 and all(a["overall"] > 0 for a in arms)
        return (ok, "status=done，2 个臂均产出综合分",
                f"status={row['status']} arms={[(a['strategy_name'], a['recall'], a['overall'], a['avg_cost_ms']) for a in arms]} err={row['error'][:60]}")

    R.case("E2E-8.4", "功能", "策略对比看板 2 臂产出综合分", compare_done)

    # ---------------- 9. 稳定性 ----------------
    print("\n== 9 并发与稳定性 ==")
    def concurrent_upload():
        name = f"并发压测_{ts}.md"
        ids = [api.upload(kb_id, f"{name[:-3]}_{i}.md", (DOCS["员工考勤与假期制度.md"] * 2).encode("utf-8"))[1]
               for i in range(8)]
        new_ids = [x["data"]["id"] for x in ids if x.get("code") == 0]
        t0 = time.time()
        states = {}
        # 注意：必须等「全部进入终态(parsed/failed)」才退出轮询。
        # 若只等「每个 id 都出现过状态」，parsing 会被误当已收敛，导致刚上传完就断言失败。
        while time.time() - t0 < 90:
            _, p = api.get("/api/document/page", params={"kb_id": kb_id, "page": 1, "page_size": 100})
            states = {row["id"]: row["status"] for row in p["data"]["list"] if row["id"] in new_ids}
            if len(states) == len(new_ids) and all(s in ("parsed", "failed") for s in states.values()):
                break
            time.sleep(1)
        created["docs"].extend(new_ids)
        ok = len(states) == len(new_ids) and all(s in ("parsed", "failed") for s in states.values())
        parsed = [k for k, v in states.items() if v == "parsed"]
        return (ok and len(parsed) == len(new_ids), f"{len(new_ids)} 个并发上传全部进入终态且解析成功",
                f"终态={states}")

    R.case("E2E-9.1", "稳定性", "并发上传 8 个文档后台任务不丢失", concurrent_upload)

    def health():
        _, r = api.get("/api/health")
        return (r.get("code") == 0, "code=0", str(r.get("data")))

    R.case("E2E-9.2", "稳定性", "全链路跑完后服务健康", health)

    # ---------------- 清理 ----------------
    print("\n== 清理沙箱数据 ==")
    n = 0
    for sid in created["sessions"]:
        n += api.delete(f"/api/chat/session/{sid}")[1].get("code") == 0
    for d in created["docs"]:
        n += api.delete(f"/api/document/{d}")[1].get("code") == 0
    for aid in (app_id, agent_app_id):
        n += api.delete(f"/api/chatApp/{aid}")[1].get("code") == 0
    if created["dataset"]:
        n += api.delete(f"/api/eval/dataset/{created['dataset']}")[1].get("code") == 0
    if created["run"]:
        api.delete(f"/api/eval/run/{created['run']}")
    if created["cmp"]:
        api.delete(f"/api/eval/compare/{created['cmp']}")
    for sid in created["strategies"]:
        n += api.delete(f"/api/retrievalStrategy/{sid}")[1].get("code") == 0
    if created["kb"]:
        n += api.delete(f"/api/knowledgeBase/{created['kb']}")[1].get("code") == 0
    for mid in created["models"]:
        n += api.delete(f"/api/aiModel/{mid}")[1].get("code") == 0
    print(f"已清理 {n} 项沙箱数据")

    out = R.dump(Path(__file__).resolve().parent / "results" / "e2e_results.json")
    s = R.stats
    print(f"\n===== 端到端测试汇总：{s['passed']}/{s['total']} 通过，{s['failed']} 失败，耗时 {s['duration_s']}s =====")
    print(f"原始结果：{out}")
    print(f"Mock 调用统计：{mock.state()}")
    return 1 if s["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())

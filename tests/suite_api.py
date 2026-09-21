"""接口层测试套件（黑盒，不依赖 Mock 大模型）：契约 / 鉴权 / 边界 / 安全 / 权限。

覆盖模块：
    A 登录注册        B 会话鉴权(JWT)      C 权限与越权
    D 用户管理        E 知识库与文档        F 策略与配置
    G 对话与会话      H 评测与Agent         I 仪表盘与日志
    J 接口契约一致性   K 安全（注入/XSS/穿越/类型）
    R 历史缺陷回归
运行：python suite_api.py       （结果落 results/api_results.json）
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Api, ApiError, Report  # noqa: E402

R = Report("接口层测试")


def main() -> int:
    api = Api()
    api.login()
    admin_token = api.token
    ts = int(time.time())
    created_users, created_kbs, created_docs = [], [], []
    pending = {}   # 供后续用例引用的临时数据

    # ---------------- A 登录注册 ----------------
    print("\n== A 登录注册 ==")
    R.case("A1", "功能", "admin 正确账号密码登录", lambda: (
        lambda r: (r[1].get("code") == 0 and bool(r[1]["data"].get("token")), "code=0 且返回 token", r[1].get("msg")))(api.post("/api/login", json_body={"username": "admin", "password": "admin"})))
    R.case("A2", "功能", "密码错误被拒且不返回 token", lambda: (
        lambda r: (r[1].get("code") != 0 and not r[1].get("data"), "code!=0 且 data 为空", r[1]["msg"]))(api.post("/api/login", json_body={"username": "admin", "password": "wrong-pwd"})))
    R.case("A3", "边界", "账号不存在被拒", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.post("/api/login", json_body={"username": "no_such_user_xyz", "password": "x"})))
    R.case("A4", "边界", "空账号空密码被拒", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.post("/api/login", json_body={"username": "", "password": ""})))
    R.case("A5", "异常", "非法 JSON 体不返回 500", lambda: (
        lambda r: (r[0] == 200 and r[1].get("code") != 0, "HTTP 200 且 code!=0（友好报错）", f"{r[0]} {r[1].get('msg')}"))(api.request("POST", "/api/login", raw_body=b"{not-json", content_type="application/json")))
    R.case("A6", "边界", "注册超短账号被拒", lambda: (
        lambda r: (r[1].get("code") != 0 and "2" in str(r[1]["msg"]), "code!=0 提示至少2个字符", r[1]["msg"]))(api.post("/api/register", json_body={"username": "a", "password": "1234"})))
    R.case("A7", "边界", "注册超短密码被拒", lambda: (
        lambda r: (r[1].get("code") != 0 and "4" in str(r[1]["msg"]), "code!=0 提示至少4位", r[1]["msg"]))(api.post("/api/register", json_body={"username": f"t_usr_{ts}", "password": "12"})))
    R.case("A8", "功能", "注册新用户成功并可直接登录", lambda: (
        lambda reg, lg: (reg[1].get("code") == 0 and lg[1].get("code") == 0, "注册 code=0 且登录 code=0", f"注册={reg[1].get('msg')} 登录={lg[1].get('msg')}"))(
        api.post("/api/register", json_body={"username": f"t_usr_{ts}", "password": "test1234", "nickname": "测试用户"}),
        api.post("/api/login", json_body={"username": f"t_usr_{ts}", "password": "test1234"})))
    R.case("A9", "边界", "重复账号注册被拒", lambda: (
        lambda r: (r[1].get("code") != 0 and "已被注册" in str(r[1]["msg"]), "code!=0 提示已被注册", r[1]["msg"]))(api.post("/api/register", json_body={"username": f"t_usr_{ts}", "password": "test1234"})))
    R.case("A10", "功能", "登录写入操作日志", lambda: (
        lambda r: (r[1].get("code") == 0 and int(r[1]["data"]["total"]) > 0, "日志总数>0", f"total={r[1]['data'].get('total') if r[1].get('code')==0 else r[1]['msg']}"))(api.get("/api/operationLog/page", params={"page": 1, "page_size": 5})))

    # ---------------- B 会话鉴权 ----------------
    print("\n== B 会话鉴权(JWT) ==")
    R.case("B1", "安全", "无 Token 访问需登录接口被拒", lambda: (
        lambda r: (r[0] == 200 and r[1].get("code") == 401, "code=401", f"{r[0]} {r[1].get('msg')}"))(Api().get("/api/auth/me")))
    R.case("B2", "安全", "伪造 Token 被拒", lambda: (
        lambda r: (r[1].get("code") == 401, "code=401", r[1]["msg"]))(Api(token="eyJhbGciOiJIUzI1NiJ9.forged.signature").get("/api/auth/me")))
    R.case("B3", "安全", "截断 Token 被拒", lambda: (
        lambda r: (r[1].get("code") == 401, "code=401", r[1]["msg"]))(Api(token=admin_token[:20]).get("/api/auth/me")))
    R.case("B4", "功能", "有效 Token 可读取当前用户", lambda: (
        lambda r: (r[1].get("code") == 0 and r[1]["data"]["username"] == "admin", "返回 admin", r[1].get("code")))(api.get("/api/auth/me")))
    R.case("B5", "安全", "Token 用错签名密钥被拒", lambda: (
        lambda r: (r[1].get("code") == 401, "code=401", r[1]["msg"]))(Api(token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOjEsInJvbGUiOiJhZG1pbiJ9.aaa").get("/api/auth/me")))

    # ---------------- C 权限与越权 ----------------
    print("\n== C 权限与越权 ==")
    normal = Api()
    normal_data = normal.ok_data(Api().post("/api/login", json_body={"username": f"t_usr_{ts}", "password": "test1234"}))
    normal_token = normal_data["token"]
    for cid, path, method, title in [
        ("C1", "/api/admin/user/page", "GET", "普通用户访问用户管理"),
        ("C2", "/api/operationLog/page", "GET", "普通用户访问操作日志"),
        ("C3", "/api/aiModel/page", "GET", "普通用户访问 AI 模型配置"),
        ("C4", "/api/tool/page", "GET", "普通用户访问工具中心"),
        ("C5", "/api/prompt/page", "GET", "普通用户访问 Prompt 管理"),
    ]:
        R.case(cid, "权限", title + "被拒(403)", (lambda p=path, m=method: (
            lambda r: (r[1].get("code") == 403, "code=403", r[1]["msg"]))(Api(token=normal_token).request(m, p))))
    R.case("C6", "权限", "普通用户可访问首页统计(共享数据)", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", r[1].get("msg")))(Api(token=normal_token).get("/api/dashboard/summary")))

    # ---------------- D 用户管理 ----------------
    print("\n== D 用户管理 ==")
    r = api.post("/api/admin/user", json_body={"username": f"t_mg_{ts}", "password": "pwd12345", "nickname": "被管理用户", "role": "user"})
    uid = api.ok_data(r)["id"] if r[1].get("code") == 0 else None
    created_users.append(uid)
    R.case("D1", "功能", "管理员创建用户", lambda: (uid is not None, "code=0 且返回 id", f"id={uid}, msg={r[1].get('msg')}"))
    R.case("D2", "功能", "管理员修改用户信息", lambda: (
        lambda x: (x[1].get("code") == 0, "code=0", x[1].get("msg")))(api.put(f"/api/admin/user/{uid}", json_body={"username": "", "nickname": "改名后", "email": "a@b.com", "role": "user", "status": 1})))
    R.case("D3", "功能", "禁用用户后其登录被拒", lambda: (
        lambda dis, lg: (dis[1].get("code") == 0 and lg[1].get("code") != 0, "禁用成功且登录被拒", f"禁用={dis[1].get('code')} 登录={lg[1].get('msg')}"))(
        api.put(f"/api/admin/user/{uid}/status", json_body={"status": 0}),
        Api().post("/api/login", json_body={"username": f"t_mg_{ts}", "password": "pwd12345"})))
    R.case("D4", "功能", "重新启用用户后登录恢复", lambda: (
        lambda en, lg: (en[1].get("code") == 0 and lg[1].get("code") == 0, "启用成功且登录成功", f"启用={en[1].get('code')} 登录={lg[1].get('code')}"))(
        api.put(f"/api/admin/user/{uid}/status", json_body={"status": 1}),
        Api().post("/api/login", json_body={"username": f"t_mg_{ts}", "password": "pwd12345"})))
    R.case("D5", "功能", "管理员重置用户密码后新密码可登录", lambda: (
        lambda rp, lg: (rp[1].get("code") == 0 and lg[1].get("code") == 0, "重置成功且新密码可登录", f"重置={rp[1].get('code')} 登录={lg[1].get('code')}"))(
        api.put(f"/api/admin/user/{uid}/password", json_body={"password": "newpwd999"}),
        Api().post("/api/login", json_body={"username": f"t_mg_{ts}", "password": "newpwd999"})))
    R.case("D6", "边界", "重置密码过短被拒", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.put(f"/api/admin/user/{uid}/password", json_body={"password": "1"})))
    R.case("D7", "边界", "管理员不能删除自己", lambda: (
        lambda r: (r[1].get("code") != 0 and "自己" in str(r[1]["msg"]), "code!=0 提示不能删除自己", r[1]["msg"]))(api.delete("/api/admin/user/1")))
    R.case("D8", "边界", "操作不存在的用户返回友好提示", lambda: (
        lambda r: (r[1].get("code") != 0 and "不存在" in str(r[1]["msg"]), "code!=0 提示用户不存在", r[1]["msg"]))(api.put("/api/admin/user/99999999", json_body={"username": "", "nickname": "x", "role": "user", "status": 1})))
    R.case("D9", "边界", "分页 page=0 与超大 page_size 被安全收敛", lambda: (
        lambda r: (r[1].get("code") == 0 and r[1]["data"]["page"] >= 1, "code=0 且 page>=1", f"page={r[1]['data'].get('page')} size={r[1]['data'].get('page_size')}"))(api.get("/api/admin/user/page", params={"page": 0, "page_size": 99999})))
    R.case("D10", "边界", "分页传非数字被安全拒绝(类型校验)", lambda: (
        # common/utils.get_page 内部对坏值有 try/except 容错，但路由签名声明为 int，
        # FastAPI 会在进入函数前就做类型校验并返回明确错误。
        # 经评估：对畸形分页参数返回清晰错误优于静默兜底，故以「显式拒绝」为期望行为。
        lambda r: (r[1].get("code") != 0 and "参数错误" in str(r[1].get("msg")), "code!=0 明确参数错误", f"{r[1].get('msg')}"))(api.get("/api/admin/user/page", params={"page": "abc", "page_size": "xyz"})))
    R.case("D11", "功能", "用户模糊查询命中昵称/账号", lambda: (
        # 注意：D2 已把昵称从「被管理用户」改成「改名后」，这里必须用当前昵称或账号，
        # 否则查的是被改掉的历史昵称，恒为 0 命中（测试数据维护问题，非产品缺陷）。
        lambda r: (r[1].get("code") == 0 and int(r[1]["data"]["total"]) >= 1, "total>=1", f"total={r[1]['data'].get('total')}"))(api.get("/api/admin/user/page", params={"query": "改名后", "page": 1, "page_size": 10})))
    R.case("D12", "功能", "删除用户成功", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", r[1].get("msg")))(api.delete(f"/api/admin/user/{uid}")))

    # ---------------- E 知识库与文档 ----------------
    print("\n== E 知识库与文档 ==")
    emb = api.post("/api/aiModel", json_body={"name": f"测试向量模型_{ts}", "type": "embedding", "model": "mock-embedding",
                                             "api_base": "http://mock-llm:8000/v1", "api_key": "sk-test", "dimension": 1024})
    emb_id = api.ok_data(emb)["id"]
    R.case("E1", "功能", "创建知识库(绑定向量模型)", lambda: (
        lambda r: (r[1].get("code") == 0 and r[1]["data"].get("id"), "code=0 且返回 id", r[1].get("msg")))(api.post("/api/knowledgeBase", json_body={"name": f"测试知识库_{ts}", "description": "自动化测试", "vector_model_id": emb_id})))
    kb = api.post("/api/knowledgeBase", json_body={"name": f"测试知识库2_{ts}", "vector_model_id": emb_id})
    kb_id = api.ok_data(kb)["id"]
    created_kbs.append(kb_id)
    R.case("E2", "边界", "名称为空建库被拒", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.post("/api/knowledgeBase", json_body={"name": "   ", "vector_model_id": emb_id})))
    R.case("E3", "边界", "未选向量模型建库被拒(业务友好校验)", lambda: (
        lambda r: (r[1].get("code") != 0 and "向量模型" in str(r[1]["msg"]), "code!=0 提示请选择向量模型", r[1]["msg"]))(api.post("/api/knowledgeBase", json_body={"name": "x", "vector_model_id": None})))
    R.case("E4", "功能", "知识库分页返回统计字段", lambda: (
        lambda r: (r[1].get("code") == 0 and all(k in r[1]["data"]["list"][0] for k in ("doc_count", "chunk_count", "vector_count")) if r[1]["data"]["list"] else False, "含 doc_count/chunk_count/vector_count", str(r[1]["data"]["list"][0].keys())[:150] if r[1]["data"]["list"] else "空"))(api.get("/api/knowledgeBase/page", params={"page": 1, "page_size": 10})))
    R.case("E5", "功能", "知识库模糊查询", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", f"total={r[1]['data'].get('total')}"))(api.get("/api/knowledgeBase/page", params={"query": "测试知识库", "page": 1, "page_size": 10})))
    R.case("E6", "功能", "修改知识库名称", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", r[1].get("msg")))(api.put(f"/api/knowledgeBase/{kb_id}", json_body={"name": f"改名知识库_{ts}", "vector_model_id": emb_id})))
    R.case("E7", "边界", "重建不存在的知识库索引友好报错", lambda: (
        lambda r: (r[1].get("code") != 0 and "不存在" in str(r[1]["msg"]), "code!=0 提示知识库不存在", r[1]["msg"]))(api.post("/api/knowledgeBase/99999999/rebuild")))
    R.case("E8", "异常", "上传不支持的文件类型被拒", lambda: (
        lambda r: (r[1].get("code") != 0 and "不支持" in str(r[1]["msg"]), "code!=0 提示不支持", r[1]["msg"]))(api.upload(kb_id, "trojan.exe", b"MZ\x90\x00fake")))
    R.case("E9", "功能", "上传 txt 文档成功并返回 doc_id", lambda: (
        lambda r: (r[1].get("code") == 0 and r[1]["data"].get("id"), "code=0 且返回 id", r[1].get("msg")))(api.upload(kb_id, f"接口测试_{ts}.txt", "接口测试文档内容。".encode("utf-8"))))
    up = api.upload(kb_id, f"接口测试2_{ts}.txt", "第二份文档。".encode("utf-8"))
    if up[1].get("code") == 0:
        created_docs.append(up[1]["data"]["id"])
    R.case("E10", "边界", "上传到不存在的知识库被拒", lambda: (
        lambda r: (r[1].get("code") != 0 and "知识库不存在" in str(r[1]["msg"]), "code!=0", r[1]["msg"]))(api.upload(99999999, "a.txt", b"x")))
    R.case("E11", "功能", "文档分页按知识库过滤", lambda: (
        lambda r: (r[1].get("code") == 0 and r[1]["data"]["total"] >= 1, "total>=1", f"total={r[1]['data'].get('total')}"))(api.get("/api/document/page", params={"kb_id": kb_id, "page": 1, "page_size": 10})))
    R.case("E12", "边界", "文档分页传不存在的 kb_id 返回空列表", lambda: (
        lambda r: (r[1].get("code") == 0 and r[1]["data"]["total"] == 0, "code=0 且 total=0", f"total={r[1]['data'].get('total')}"))(api.get("/api/document/page", params={"kb_id": 99999999, "page": 1, "page_size": 10})))
    R.case("E13", "边界", "重解析不存在的文档友好报错", lambda: (
        lambda r: (r[1].get("code") != 0 and "不存在" in str(r[1]["msg"]), "code!=0", r[1]["msg"]))(api.post("/api/document/99999999/reparse")))
    R.case("E14", "功能", "片段分页(按文档过滤)", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", f"total={r[1]['data'].get('total')}"))(api.get("/api/chunk/page", params={"doc_id": created_docs[0] if created_docs else 0, "page": 1, "page_size": 10})))
    R.case("E15", "边界", "读取不存在的片段友好报错", lambda: (
        lambda r: (r[1].get("code") != 0 and "不存在" in str(r[1]["msg"]), "code!=0", r[1]["msg"]))(api.get("/api/chunk/99999999")))
    R.case("E16", "边界", "检索不存在的知识库友好报错", lambda: (
        lambda r: (r[1].get("code") != 0 and "不存在" in str(r[1]["msg"]), "code!=0 提示知识库不存在", r[1]["msg"]))(api.post("/api/retrieval/test", json_body={"kb_id": 99999999, "query": "x"})))
    R.case("E17", "边界", "召回对比不传策略被拒", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.post("/api/retrieval/compare", json_body={"kb_id": kb_id, "query": "x", "strategy_ids": []})))
    R.case("E18", "边界", "召回对比超过4套策略被拒", lambda: (
        lambda r: (r[1].get("code") != 0 and "4" in str(r[1]["msg"]), "code!=0 提示最多4套", r[1]["msg"]))(api.post("/api/retrieval/compare", json_body={"kb_id": kb_id, "query": "x", "strategy_ids": [1, 2, 3, 4, 5]})))
    R.case("E19", "边界", "召回对比不存在的知识库友好报错", lambda: (
        lambda r: (r[1].get("code") != 0 and "不存在" in str(r[1]["msg"]), "code!=0", r[1]["msg"]))(api.post("/api/retrieval/compare", json_body={"kb_id": 99999999, "query": "x", "strategy_ids": [1, 2]})))

    # ---------------- F 策略与配置 ----------------
    print("\n== F 策略与配置 ==")
    e = api.post("/api/splitStrategy", json_body={"name": f"测试切分_{ts}", "mode": "recursive", "chunk_size": 300, "chunk_overlap": 30})
    sid = api.ok_data(e)["id"]
    R.case("F1", "功能", "创建切分策略(递归)", lambda: (True, "code=0", f"id={sid}"))
    R.case("F2", "边界", "切分策略非法 mode 被拒", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.post("/api/splitStrategy", json_body={"name": "x", "mode": "bogus"})))
    R.case("F3", "功能", "修改切分策略", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", r[1].get("msg")))(api.put(f"/api/splitStrategy/{sid}", json_body={"name": f"测试切分改_{ts}", "mode": "parent_child", "chunk_size": 400, "chunk_overlap": 40, "parent_chunk_size": 1200, "parent_chunk_overlap": 80})))
    R.case("F4", "功能", "切分策略被知识库绑定时禁止删除", lambda: (
        lambda b, d: (b[1].get("code") == 0 and d[1].get("code") != 0 and "绑定" in str(d[1]["msg"]), "删除被拒并提示已绑定",
                      f"绑定={b[1].get('code')} 删除={d[1].get('msg')}"))(
        api.put(f"/api/knowledgeBase/{kb_id}", json_body={"name": f"改名知识库_{ts}", "split_strategy_id": sid, "vector_model_id": emb_id}),
        api.delete(f"/api/splitStrategy/{sid}")))
    R.case("F5", "功能", "删除检索策略成功", lambda: (
        lambda c, d: (c[1].get("code") == 0 and d[1].get("code") == 0, "创建与删除均 code=0", f"创建={c[1].get('code')} 删除={d[1].get('code')}"))(
        api.post("/api/retrievalStrategy", json_body={"name": f"测试检索_{ts}", "rewrite_mode": "hyde"}),
        api.delete(f"/api/retrievalStrategy/{api.get('/api/retrievalStrategy/page', params={'query': f'测试检索_{ts}', 'page':1, 'page_size':10})[1]['data']['list'][0]['id']}")))
    R.case("F6", "边界", "检索策略非法 rewrite_mode 被拒", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.post("/api/retrievalStrategy", json_body={"name": "x", "rewrite_mode": "bogus"})))
    R.case("F7", "功能", "模型配置列表不回传 api_key 明文", lambda: (
        lambda r: (r[1].get("code") == 0 and all("api_key" not in it for it in r[1]["data"]["list"]), "列表项不含 api_key 字段",
                   str([it for it in r[1]["data"]["list"] if "api_key" in it])[:120]))(api.get("/api/aiModel/page", params={"page": 1, "page_size": 20})))
    R.case("F8", "边界", "模型配置非法 type 被拒", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.post("/api/aiModel", json_body={"name": "x", "type": "bogus", "model": "m"})))
    def conn_test_bad():
        """错误地址的连通性测试：必须 code=0 友好失败，而不是抛 500 打崩接口"""
        c = api.post("/api/aiModel", json_body={"name": f"测试对话模型_bad_{ts}", "type": "chat",
                                                "model": "qwen-plus", "api_base": "http://127.0.0.1:1/v1", "api_key": "sk-bad"})
        mid = api.ok_data(c)["id"]
        r = api.post(f"/api/aiModel/{mid}/test")
        api.delete(f"/api/aiModel/{mid}")
        return (r[1].get("code") == 0 and r[1]["data"].get("ok") is False,
                "code=0 且 data.ok=false（友好失败）",
                str(r[1]["data"].get("info") or r[1].get("msg"))[:140])

    R.case("F9", "异常", "模型连通性测试失败时友好返回 ok=false", conn_test_bad)
    R.case("F10", "功能", "Prompt 内置模板导入幂等", lambda: (
        lambda a, b: (a[1].get("code") == 0 and b[1].get("code") == 0, "两次调用均 code=0",
                      f"第一次新增={a[1]['data'].get('created')} 第二次新增={b[1]['data'].get('created')}"))(
        api.post("/api/prompt/import_builtin"), api.post("/api/prompt/import_builtin")))
    R.case("F11", "功能", "工具内置导入幂等", lambda: (
        lambda a, b: (a[1].get("code") == 0 and b[1].get("code") == 0, "两次调用均 code=0",
                      f"第一次新增={a[1]['data'].get('created')} 第二次新增={b[1]['data'].get('created')}"))(
        api.post("/api/tool/import_builtin"), api.post("/api/tool/import_builtin")))
    R.case("F12", "功能", "工具手动执行-计算器", lambda: (
        lambda r: (r[1].get("code") == 0 and "42" in str(r[1]["data"]["result"]), "计算结果含 42", str(r[1]["data"].get("result"))[:80]))(
        api.post("/api/tool/execute", json_body={"code": "calculator", "args": {"expression": "6*7"}})))
    R.case("F13", "异常", "工具执行-非法表达式不崩溃", lambda: (
        lambda r: (r[1].get("code") == 0 and "失败" in str(r[1]["data"]["result"]), "code=0 且提示计算失败", str(r[1]["data"].get("result"))[:80]))(
        api.post("/api/tool/execute", json_body={"code": "calculator", "args": {"expression": "__import__('os').system('ls')"}})))
    R.case("F14", "异常", "执行不存在的工具友好报错", lambda: (
        lambda r: (r[1].get("code") == 0 and "未实现" in str(r[1]["data"]["result"]), "code=0 且提示未实现处理器", str(r[1]["data"].get("result"))[:80]))(
        api.post("/api/tool/execute", json_body={"code": "no_such_tool", "args": {}})))
    app_r = api.post("/api/chatApp", json_body={"name": f"测试应用_{ts}", "description": "自动化", "use_agent": 0})
    R.case("F15", "功能", "创建问答应用", lambda: (
        app_r[1].get("code") == 0 and bool(app_r[1].get("data") or {}), "code=0 且返回 id", str(app_r[1].get("msg"))))
    pending["app_id"] = api.ok_data(api.post("/api/chatApp", json_body={"name": f"测试应用2_{ts}", "use_agent": 0}))["id"]
    R.case("F16", "功能", "应用绑定知识库", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", r[1].get("msg")))(api.put(f"/api/chatApp/{pending['app_id']}/kbs", json_body={"kb_ids": [kb_id]})))
    R.case("F17", "功能", "应用列表回带绑定的知识库名称", lambda: (
        lambda r: (r[1].get("code") == 0 and any(it.get("kb_ids") for it in r[1]["data"]["list"]), "存在已绑定知识库的应用",
                   str([(it["name"], it.get("kb_names")) for it in r[1]["data"]["list"] if it.get("kb_ids")])[:160]))(api.get("/api/chatApp/page", params={"page": 1, "page_size": 20})))
    R.case("F18", "边界", "绑定不存在的知识库被静默忽略", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", r[1].get("msg")))(api.put(f"/api/chatApp/{pending['app_id']}/kbs", json_body={"kb_ids": [99999999]})))

    # ---------------- G 对话与会话 ----------------
    print("\n== G 对话与会话 ==")
    R.case("G1", "边界", "创建会话时应用不存在被拒", lambda: (
        lambda r: (r[1].get("code") != 0 and "不存在" in str(r[1]["msg"]), "code!=0", r[1]["msg"]))(api.post("/api/chat/session", json_body={"app_id": 99999999})))
    sess = api.post("/api/chat/session", json_body={"app_id": pending["app_id"], "title": "自动化测试会话"})
    sid = api.ok_data(sess)["id"]
    R.case("G2", "功能", "创建会话成功", lambda: (True, "code=0", f"session_id={sid}"))
    R.case("G3", "功能", "会话列表分页", lambda: (
        lambda r: (r[1].get("code") == 0 and r[1]["data"]["total"] >= 1, "total>=1", f"total={r[1]['data'].get('total')}"))(api.get("/api/chat/session/page", params={"page": 1, "page_size": 50})))
    R.case("G4", "边界", "查询不存在会话历史不崩溃", lambda: (
        lambda r: (r[1].get("code") != 0 and "不存在" in str(r[1]["msg"]), "code!=0 友好提示", r[1]["msg"]))(api.get("/api/chat/history/99999999")))
    R.case("G5", "边界", "会话ID=0 查询不崩溃", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.get("/api/chat/history/0")))
    R.case("G6", "边界", "会话ID=-1 查询不崩溃", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.get("/api/chat/history/-1")))
    R.case("G7", "边界", "反馈不存在的消息友好报错", lambda: (
        lambda r: (r[1].get("code") != 0 and "不存在" in str(r[1]["msg"]), "code!=0", r[1]["msg"]))(api.post("/api/chat/feedback", json_body={"message_id": 99999999, "feedback": "useful"})))
    def empty_query():
        """空问题在进入 SSE 之前就应被业务校验拦截为 code!=0"""
        s = api.post("/api/chat/session", json_body={"app_id": pending["app_id"], "title": "空问题用例"})
        sid2 = api.ok_data(s)["id"]
        r = api.post("/api/chat/ask", json_body={"session_id": sid2, "query": "   "})
        api.delete(f"/api/chat/session/{sid2}")
        return (r[1].get("code") != 0 and "不能为空" in str(r[1].get("msg")),
                "code!=0 且提示问题不能为空", f"{r[0]} {str(r[1].get('msg'))[:120]}")

    R.case("G8", "边界", "空问题提问被业务校验拦截", empty_query)
    R.case("G9", "功能", "删除会话成功", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", r[1].get("msg")))(api.delete(f"/api/chat/session/{sid}")))

    # ---------------- H 评测与 Agent ----------------
    print("\n== H 评测与 Agent ==")
    R.case("H1", "功能", "创建评测集", lambda: (
        lambda r: (r[1].get("code") == 0 and r[1]["data"].get("id"), "code=0", r[1].get("msg")))(api.post("/api/eval/dataset", json_body={"name": f"测试评测集_{ts}", "kb_id": kb_id})))
    ds = api.post("/api/eval/dataset", json_body={"name": f"测试评测集2_{ts}", "kb_id": kb_id})
    ds_id = api.ok_data(ds)["id"]
    R.case("H2", "功能", "评测用例创建", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", r[1].get("msg")))(api.post("/api/eval/case", params={"dataset_id": ds_id}, json_body={"question": "测试问题", "ground_truth": "参考答案", "source_chunk_ids": [1, 2]})))
    R.case("H3", "边界", "空问题用例被拒", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.post("/api/eval/case", params={"dataset_id": ds_id}, json_body={"question": "  "})))
    def batch_import():
        r = api.post("/api/eval/case/batch", params={"dataset_id": ds_id},
                     json_body={"cases": [{"question": "问题A", "source_chunk_ids": [3]},
                                          {"question": "问题B", "ground_truth": "答B"}]})
        return (r[1].get("code") == 0 and r[1]["data"]["created"] == 2, "created=2", str(r[1].get("data")))

    R.case("H4", "功能", "用例批量导入", batch_import)
    R.case("H5", "边界", "空用例批量导入被拒", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.post("/api/eval/case/batch", params={"dataset_id": ds_id}, json_body={"cases": []})))
    R.case("H6", "边界", "用例分页缺少 dataset_id 被参数校验拦截", lambda: (
        lambda r: (r[1].get("code") != 0 and "dataset_id" in str(r[1]["msg"]), "code!=0 提示 dataset_id", str(r[1]["msg"])[:120]))(api.get("/api/eval/case/page", params={"page": 1, "page_size": 10})))
    R.case("H7", "边界", "空评测集启动评测被拒", lambda: (
        lambda r: (r[1].get("code") != 0 and "用例" in str(r[1]["msg"]), "code!=0 提示先导入用例", r[1]["msg"]))(api.post("/api/eval/run", json_body={"dataset_id": 99999999, "kb_id": kb_id})))
    R.case("H8", "边界", "策略对比少于2套被拒", lambda: (
        lambda r: (r[1].get("code") != 0 and "2" in str(r[1]["msg"]), "code!=0 提示需 2~4 套", r[1]["msg"]))(api.post("/api/eval/compare", json_body={"kb_id": kb_id, "dataset_id": ds_id, "strategy_ids": [1]})))
    R.case("H9", "功能", "评测运行分页可用", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", f"total={r[1]['data'].get('total')}"))(api.get("/api/eval/run/page", params={"page": 1, "page_size": 10})))
    R.case("H10", "功能", "策略对比分页可用", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", f"total={r[1]['data'].get('total')}"))(api.get("/api/eval/compare/page", params={"page": 1, "page_size": 10})))
    R.case("H11", "边界", "Agent 运行参数缺失被校验拦截", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", str(r[1]["msg"])[:120]))(api.post("/api/agent/run", json_body={"query": "x"})))
    R.case("H12", "边界", "Agent 运行应用不存在友好报错", lambda: (
        lambda r: (r[1].get("code") != 0 and "不存在" in str(r[1]["msg"]), "code!=0", r[1]["msg"]))(api.post("/api/agent/run", json_body={"app_id": 99999999, "query": "x"})))
    R.case("H13", "边界", "Agent 不存在的运行记录友好报错", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.get("/api/agent/run/99999999")))
    R.case("H14", "功能", "Agent 步骤查询不存在运行返回空数组", lambda: (
        lambda r: (r[1].get("code") == 0 and r[1]["data"] == [], "code=0 且 data=[]", str(r[1]["data"])[:80]))(api.get("/api/agent/steps/99999999")))
    R.case("H15", "功能", "Agent 运行记录模糊查询", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", f"total={r[1]['data'].get('total')}"))(api.get("/api/agent/runPage", params={"query": "测试", "page": 1, "page_size": 10})))

    # ---------------- I 仪表盘与日志 ----------------
    print("\n== I 仪表盘与日志 ==")
    R.case("I1", "功能", "首页统计返回 12 项指标", lambda: (
        lambda r: (r[1].get("code") == 0 and all(k in r[1]["data"] for k in
                   ("kb", "doc", "chunk", "user", "app", "question", "agent_run", "optimize", "vector", "model", "eval_run", "failed_doc")),
                   "12 项指标齐备", str(sorted(r[1]["data"].keys() - {"architecture"}))[:200]))(api.get("/api/dashboard/summary")))
    R.case("I2", "功能", "首页统计返回架构说明", lambda: (
        lambda r: (r[1].get("code") == 0 and "architecture" in r[1]["data"], "含 architecture", str(list(r[1]["data"].get("architecture", {}).keys()))[:150]))(api.get("/api/dashboard/summary")))
    R.case("I3", "功能", "操作日志分页", lambda: (
        lambda r: (r[1].get("code") == 0 and r[1]["data"]["total"] >= 1, "total>=1", f"total={r[1]['data'].get('total')}"))(api.get("/api/operationLog/page", params={"page": 1, "page_size": 10})))
    R.case("I4", "功能", "工具调用日志分页", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", f"total={r[1]['data'].get('total')}"))(api.get("/api/tool/log/page", params={"page": 1, "page_size": 10})))
    R.case("I5", "功能", "健康检查接口", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0", str(r[1]["data"])))(api.get("/api/health")))

    # ---------------- J 契约一致性 ----------------
    print("\n== J 契约一致性（统一 {code,msg,data}）==")
    contract_paths = [
        ("GET", "/api/dashboard/summary"), ("GET", "/api/knowledgeBase/page"), ("GET", "/api/document/page"),
        ("GET", "/api/chunk/page"), ("GET", "/api/aiModel/page"), ("GET", "/api/prompt/page"),
        ("GET", "/api/tool/page"), ("GET", "/api/chatApp/page"), ("GET", "/api/retrievalStrategy/page"),
        ("GET", "/api/splitStrategy/page"), ("GET", "/api/eval/dataset/page"), ("GET", "/api/eval/run/page"),
        ("GET", "/api/eval/compare/page"), ("GET", "/api/admin/user/page"), ("GET", "/api/operationLog/page"),
        ("GET", "/api/auth/me"), ("GET", "/api/health"), ("GET", "/api/tool/log/page"),
        ("GET", "/api/agent/runPage"), ("GET", "/api/chat/session/page"), ("GET", "/api/chatApp/options"),
    ]

    def contract_check():
        bad = []
        for method, p in contract_paths:
            st, body = api.request(method, p)
            if not isinstance(body, dict) or not {"code", "msg", "data"} <= set(body.keys()):
                bad.append(f"{p} -> {str(body)[:80]}")
        return (not bad, f"{len(contract_paths)} 个接口均为 code/msg/data", f"不符合：{bad}" if bad else "全部符合")

    R.case("J1", "契约", "核心接口统一返回结构", contract_check)

    # ---------------- K 安全 ----------------
    print("\n== K 安全测试 ==")
    injections = ["admin' OR '1'='1", "admin'; DROP TABLE user--", "admin' UNION SELECT 1,2--", "admin'--", "\" or \"\"=\""]
    R.case("K1", "安全", "登录 SQL 注入全部被拒且无 token 泄漏", lambda: (
        (lambda rs: (all(r[1].get("code") != 0 for r in rs) and all(not r[1].get("data") for r in rs),
                     "5 条注入均 code!=0 且 data 为空", f"{[(i, r[1].get('msg')) for i, r in zip(injections, rs)]}"[:300]))(
            [api.post("/api/login", json_body={"username": i, "password": i}) for i in injections])))
    R.case("K2", "安全", "查询参数注入无法绕过参数化查询", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0 正常返回", f"total={r[1]['data'].get('total')}"))(
        api.get("/api/knowledgeBase/page", params={"query": "' OR 1=1--", "page": 1, "page_size": 10})))
    R.case("K3", "安全", "XSS 载荷入库后原样存储不执行", lambda: (
        lambda c, g: (c[1].get("code") == 0 and g[1].get("code") == 0 and "<script>" in str(g[1]["data"]["list"][0]["name"]),
                      "存储成功且原样返回（前端转义）", f"name={g[1]['data']['list'][0]['name'] if g[1]['data']['list'] else '空'}"))(
        api.post("/api/knowledgeBase", json_body={"name": f"<script>alert(1)</script>_{ts}", "vector_model_id": emb_id}),
        api.get("/api/knowledgeBase/page", params={"query": "<script>alert(1)</script>", "page": 1, "page_size": 10})))

    def traversal_check():
        st, body = api.upload(kb_id, "../../../../tmp/evil.txt", b"traversal-test")
        if body.get("code") != 0:
            return (False, "上传成功", str(body.get("msg")))
        doc_id = body["data"]["id"]
        _, page = api.get("/api/document/page", params={"kb_id": kb_id, "page": 1, "page_size": 50})
        row = next((x for x in page["data"]["list"] if x["id"] == doc_id), None)
        fp = (row or {}).get("file_path", "")
        ok = fp.startswith("/app/uploads/") and ".." not in fp
        created_docs.append(doc_id)
        return (ok, "落盘路径被限制在 /app/uploads 下", f"file_path={fp}")

    R.case("K4", "安全", "上传文件名的路径穿越被阻断", traversal_check)
    R.case("K5", "安全", "参数类型攻击被校验拦截", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0（参数校验）", str(r[1]["msg"])[:120]))(
        api.get("/api/document/page", params={"kb_id": "abc", "page": 1, "page_size": 10})))
    R.case("K6", "安全", "超大分页参数被上限截断", lambda: (
        lambda r: (r[1].get("code") == 0 and r[1]["data"]["page_size"] <= 200, "page_size<=200", f"page_size={r[1]['data'].get('page_size')}"))(
        api.get("/api/document/page", params={"page": 1, "page_size": 100000})))

    # ---------------- R 回归 ----------------
    print("\n== R 历史缺陷 & 本轮回归 ==")
    R.case("R1", "回归", "工具列表模糊查询可用（QuerySet OR 融合缺陷）", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0（修复前为服务器内部错误）", str(r[1].get("msg"))[:160]))(
        api.get("/api/tool/page", params={"query": "calc", "page": 1, "page_size": 20})))
    R.case("R2", "回归", "Prompt 列表模糊查询可用（QuerySet OR 融合缺陷）", lambda: (
        lambda r: (r[1].get("code") == 0, "code=0（修复前为服务器内部错误）", str(r[1].get("msg"))[:160]))(
        api.get("/api/prompt/page", params={"query": "qa_answer", "page": 1, "page_size": 20})))
    R.case("R3", "回归", "检索不存在的知识库仍为友好提示", lambda: (
        lambda r: (r[1].get("code") != 0 and "不存在" in str(r[1]["msg"]), "code!=0 提示知识库不存在", r[1]["msg"]))(
        api.post("/api/retrieval/test", json_body={"kb_id": 99999999, "query": "x"})))
    R.case("R4", "回归", "查询不存在会话历史不崩溃", lambda: (
        lambda r: (r[1].get("code") != 0, "code!=0", r[1]["msg"]))(api.get("/api/chat/history/99999999")))
    R.case("R5", "回归", "登录/知识库/模型/双策略/应用/评测核心接口全通", lambda: (
        (lambda rs: (all(r[1].get("code") == 0 for r in rs), "6 个接口 code=0",
                     f"{[r[1].get('code') for r in rs]}"))([
            api.get("/api/knowledgeBase/page"), api.get("/api/aiModel/page"), api.get("/api/prompt/page"),
            api.get("/api/splitStrategy/page"), api.get("/api/retrievalStrategy/page"), api.get("/api/eval/dataset/page")])))

    # ---------------- 清理 ----------------
    print("\n== 清理测试数据 ==")
    removed = 0
    for d in created_docs:
        if api.delete(f"/api/document/{d}")[1].get("code") == 0:
            removed += 1
    for kw in ("测试知识库", "改名知识库", "<script>alert(1)</script>"):
        for row in api.get("/api/knowledgeBase/page", params={"query": kw, "page": 1, "page_size": 50})[1]["data"]["list"]:
            api.delete(f"/api/knowledgeBase/{row['id']}")
            removed += 1
    for path, kw in (("/api/chatApp/page", "测试应用"), ("/api/eval/dataset/page", "测试评测集"),
                     ("/api/splitStrategy/page", "测试切分"), ("/api/retrievalStrategy/page", "测试检索")):
        for row in api.get(path, params={"query": kw, "page": 1, "page_size": 50})[1]["data"]["list"]:
            api.delete(f"{path.rsplit('/', 1)[0]}/{row['id']}")
            removed += 1
    for row in api.get("/api/aiModel/page", params={"page": 1, "page_size": 50})[1]["data"]["list"]:
        if row["name"].startswith(("测试向量模型", "测试对话模型", "测试重排模型")):
            api.delete(f"/api/aiModel/{row['id']}")
            removed += 1
    for row in api.get("/api/admin/user/page", params={"page": 1, "page_size": 50})[1]["data"]["list"]:
        if row["username"].startswith("t_usr_") or row["username"].startswith("t_mg_"):
            api.delete(f"/api/admin/user/{row['id']}")
            removed += 1
    print(f"已清理 {removed} 项测试数据")

    out = R.dump(Path(__file__).resolve().parent / "results" / "api_results.json")
    s = R.stats
    print(f"\n===== 接口层测试汇总：{s['passed']}/{s['total']} 通过，{s['failed']} 失败，耗时 {s['duration_s']}s =====")
    print(f"原始结果：{out}")
    return 1 if s["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())

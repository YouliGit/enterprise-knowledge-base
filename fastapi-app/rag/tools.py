"""Function Calling 工具中心：内置工具 + 日志，模型按需调用。"""
import ast
import json
import logging
import time

from models import Tool, ToolCallLog

logger = logging.getLogger(__name__)


# ---------------- 内置工具处理器 ----------------

async def _h_calculator(args: dict) -> str:
    """安全的四则运算计算器"""
    expr = str(args.get("expression", "")).strip()
    if not expr:
        return "缺少 expression 参数"

    def _safe_eval(node):
        if isinstance(node, ast.Expression):
            return _safe_eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)):
            left, right = _safe_eval(node.left), _safe_eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** right
            return left % right
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = _safe_eval(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        raise ValueError("只支持四则运算")

    try:
        val = _safe_eval(ast.parse(expr, mode="eval"))
        return f"{expr} = {val}"
    except Exception as e:
        return f"计算失败: {e}"


async def _h_current_time(args: dict) -> str:
    import datetime

    return "当前时间：" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def _h_kb_search(args: dict) -> str:
    """在指定知识库做混合检索，返回片段摘要（不生成答案）"""
    from models import KnowledgeBase
    from rag.retriever import hybrid_retrieve

    kb_id = int(args.get("kb_id", 0))
    query = str(args.get("query", ""))
    top_k = int(args.get("top_k", 3))
    kb = await KnowledgeBase.filter(id=kb_id).first()
    if not kb:
        return f"知识库 {kb_id} 不存在"
    out = await hybrid_retrieve(kb_id, query)
    lines = [f"[{c.rank}] {c.content[:200]}" for c in out.contexts[:top_k]]
    return "\n".join(lines) or "未检索到相关片段"


HANDLERS = {
    "calculator": _h_calculator,
    "current_time": _h_current_time,
    "kb_search": _h_kb_search,
}


# ---------------- 内置工具定义（写入内置工具 按钮的数据源） ----------------

BUILTIN_TOOLS = [
    {
        "code": "calculator",
        "name": "计算器",
        "description": "当需要精确的数学计算时使用。参数 expression 为四则运算表达式，如 3*(4+5)。",
        "schema_json": json.dumps({
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "四则运算计算器",
                "parameters": {
                    "type": "object",
                    "properties": {"expression": {"type": "string", "description": "算术表达式"}},
                    "required": ["expression"],
                },
            },
        }, ensure_ascii=False),
        "handler": "calculator",
    },
    {
        "code": "current_time",
        "name": "当前时间",
        "description": "当用户询问现在的时间、日期时使用，无参数。",
        "schema_json": json.dumps({
            "type": "function",
            "function": {
                "name": "current_time",
                "description": "获取当前服务器时间",
                "parameters": {"type": "object", "properties": {}},
            },
        }, ensure_ascii=False),
        "handler": "current_time",
    },
    {
        "code": "kb_search",
        "name": "知识库检索",
        "description": "当需要查询企业知识库原始资料时使用。参数 kb_id 知识库ID、query 检索词、top_k 返回条数。",
        "schema_json": json.dumps({
            "type": "function",
            "function": {
                "name": "kb_search",
                "description": "混合检索指定知识库并返回片段",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "kb_id": {"type": "integer", "description": "知识库ID"},
                        "query": {"type": "string", "description": "检索问题"},
                        "top_k": {"type": "integer", "description": "返回条数，默认3"},
                    },
                    "required": ["kb_id", "query"],
                },
            },
        }, ensure_ascii=False),
        "handler": "kb_search",
    },
]


# ---------------- 工具执行与日志 ----------------

def _normalize_schema(raw: str) -> dict | None:
    """把库里的 schema_json 规范化成 OpenAI function calling 定义，非法则返回 None。

    容忍两种写法：
      - 带外层包装：{"type":"function","function":{...}}
      - 只写内层：  {"name":..., "description":..., "parameters":{...}}
    缺失 name 或 parameters 视为非法——否则会把 {} 这类脏数据塞进 bind_tools，
    触发 "Unsupported function {}"，导致整个问答/Agent 链路全挂。
    """
    try:
        s = json.loads(raw or "{}")
    except Exception:
        return None
    if not isinstance(s, dict):
        return None
    fn = s.get("function") if isinstance(s.get("function"), dict) else s
    name = str(fn.get("name") or "").strip()
    if not name:
        return None
    params = fn.get("parameters")
    if not isinstance(params, dict):
        params = {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": str(fn.get("description") or ""),
            "parameters": params,
        },
    }


async def get_enabled_tools() -> list[dict]:
    """所有启用工具的 OpenAI function calling schema（bind_tools 用）。

    只返回通过校验的合法定义；脏数据只记警告不抛出，避免单条坏配置拖垮整条链路。
    """
    rows = await Tool.filter(enabled=1).all()
    schemas = []
    for r in rows:
        s = _normalize_schema(r.schema_json)
        if not s:
            logger.warning("工具 [%s] 的 schema_json 非法，已跳过：%r", r.code, (r.schema_json or "")[:120])
            continue
        if s["function"]["name"] != r.code:
            # 名称与 code 不一致时以 code 为准，保证 execute_tool 能按名字回查
            s["function"]["name"] = r.code
        schemas.append(s)
    return schemas


async def execute_tool(code: str, args: dict, agent_run_id: int | None = None, on_tool=None) -> str:
    """按 code 执行工具并落日志；未注册处理器时返回提示（工具仅记录，不阻断）"""
    t0 = time.time()
    tool = await Tool.filter(code=code).first()
    handler = HANDLERS.get((tool.handler if tool else "") or code)
    status, result = "ok", ""
    try:
        if handler:
            result = await handler(args or {})
        else:
            status = "failed"
            result = f"工具 {code} 未实现处理器"
    except Exception as e:
        status = "failed"
        result = f"工具执行异常: {e}"
    cost_ms = int((time.time() - t0) * 1000)
    await ToolCallLog.create(
        tool_id=tool.id if tool else None,
        tool_code=code,
        agent_run_id=agent_run_id,
        args_json=json.dumps(args or {}, ensure_ascii=False),
        result=str(result)[:8000],
        status=status,
        cost_ms=cost_ms,
    )
    if on_tool:
        try:
            await on_tool(code, args or {}, result)
        except Exception:
            pass
    return result


async def import_builtin_tools() -> int:
    """写入内置工具（管理端按钮）：存在则跳过，返回新增数量"""
    created = 0
    for item in BUILTIN_TOOLS:
        if not await Tool.filter(code=item["code"]).exists():
            await Tool.create(built_in=1, enabled=1, **item)
            created += 1
    return created

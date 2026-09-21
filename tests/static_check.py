"""后端静态检查（轻量、零依赖）：找出「引用了未导入的全局名」一类静默缺陷。

背景：本项目大量使用 try/except 兜底，`NameError` 会被 except 吞掉，表现为功能静默失效
（例如 Agent 自查节点永远走「异常默认通过」），跑接口测试也发现不了。因此需要一个静态
检查把它揪出来。

用法：
    python static_check.py [源码目录]        # 默认 ../fastapi-app
退出码：0 无问题；1 发现问题（可用于 CI 卡点）。
"""
import ast
import builtins
import sys
from pathlib import Path

SKIP_DIRS = {"__pycache__", "tests", "uploads", ".git"}


def module_bound_names(tree: ast.AST) -> set:
    """模块顶层作用域里定义/导入的名字（含函数内 import 之外的全局绑定）。"""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                if a.name == "*":
                    continue
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.comprehension,)):
            pass
    return names


def check_file(path: Path) -> list:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return [(0, f"语法错误: {e}")]
    known = module_bound_names(tree) | set(dir(builtins)) | {"__name__", "__file__", "__doc__"}
    issues = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        used, local = set(), set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Name):
                (used if isinstance(n.ctx, ast.Load) else local).add(n.id)
            elif isinstance(n, ast.arg):
                local.add(n.arg)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                local.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    local.add((a.asname or a.name).split(".")[0])
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n is not fn:
                local.add(n.name)
        missing = sorted(x for x in used - local - known if x.isidentifier() and not x.isupper())
        if missing:
            issues.append((fn.lineno, f"{fn.name}() 引用了未导入/未定义的名字: {', '.join(missing)}"))
    return issues


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "fastapi-app")
    if not root.exists():
        print(f"目录不存在: {root}")
        return 1
    total, bad = 0, 0
    for py in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in py.parts):
            continue
        total += 1
        issues = check_file(py)
        if issues:
            bad += 1
            print(f"\n[!] {py.relative_to(root)}")
            for lineno, msg in issues:
                print(f"    行{lineno}: {msg}")
    print(f"\n静态检查完成：扫描 {total} 个文件，{bad} 个文件存在可疑引用")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

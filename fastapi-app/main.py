"""入口：启动时初始化 MySQL(Tortoise) 与 PGVector，自动扫描注册 api/ 路由。

python main.py   # 默认 9090 端口
"""
import asyncio
import importlib
import logging
import pkgutil
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

import settings
from common.exceptions import (
    AuthException,
    BizException,
    biz_exception_handler,
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from rag import vectorstore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")


async def wait_mysql(retries: int = 60, delay: float = 2.0):
    from tortoise import Tortoise

    last = None
    for i in range(retries):
        try:
            await Tortoise.init(config=settings.TORTOISE_ORM)
            await Tortoise.generate_schemas(safe=True)
            log.info("MySQL 连接成功（业务库 %s）", settings.MYSQL_DB)
            return
        except Exception as e:
            last = e
            log.warning("等待 MySQL 就绪... (%s/%s) %s", i + 1, retries, e)
            await asyncio.sleep(delay)
    raise RuntimeError(f"MySQL 连接失败: {last}")


async def ensure_seed_data():
    """首启种子：admin/admin 账号 + 默认切分/检索策略（文档三-4 前置）"""
    from common.security import hash_password
    from models import RetrievalStrategy, SplitStrategy, User

    if not await User.filter(username="admin").exists():
        await User.create(username="admin", password=hash_password("admin"),
                          nickname="平台管理员", role="admin")
        log.info("已创建默认管理员 admin / admin")
    if not await SplitStrategy.exists():
        await SplitStrategy.create(
            name="默认父子分块", mode="parent_child", chunk_size=500, chunk_overlap=50,
            parent_chunk_size=1500, parent_chunk_overlap=100,
        )
        await SplitStrategy.create(
            name="精细递归分块", mode="recursive", chunk_size=300, chunk_overlap=30,
        )
        log.info("已创建默认切分策略")
    if not await RetrievalStrategy.exists():
        await RetrievalStrategy.create(
            name="基线-纯向量检索", description="仅向量召回，用作对比基线",
            bm25_top_k=0, use_rewrite=0, rerank_enabled=0,
        )
        await RetrievalStrategy.create(
            name="混合检索-标准", description="向量+BM25 RRF融合 + 多查询改写 + 重排",
        )
        await RetrievalStrategy.create(
            name="混合检索-强改写", description="多查询扩展 + 高召回，重排收紧",
            vector_top_k=12, bm25_top_k=10, rerank_top_n=6,
        )
        log.info("已创建默认检索策略")


@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.time()
    await wait_mysql()
    await ensure_seed_data()
    await vectorstore.init_pgvector()
    log.info("PGVector 初始化完成，启动耗时 %.1fs", time.time() - t0)
    yield
    from tortoise import Tortoise

    await Tortoise.close_connections()
    await vectorstore.close_pgvector()
    log.info("已优雅退出")


app = FastAPI(title="AI Agentic RAG 企业知识库平台", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一返回/异常
from fastapi.exceptions import RequestValidationError  # noqa: E402
from starlette.exceptions import HTTPException  # noqa: E402

app.add_exception_handler(BizException, biz_exception_handler)
app.add_exception_handler(AuthException, biz_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)


# 自动扫描注册 api/ 路由
def register_routers():
    import api as api_pkg

    count = 0
    for m in pkgutil.iter_modules(api_pkg.__path__):
        mod = importlib.import_module(f"api.{m.name}")
        router = getattr(mod, "router", None)
        if router is not None:
            app.include_router(router, prefix="/api")
            count += 1
    log.info("已注册 %s 个路由模块", count)


register_routers()

app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")


@app.get("/")
async def index():
    return {"name": "AI Agentic RAG 企业知识库平台", "docs": "/docs", "api_prefix": "/api"}


@app.get("/api/health")
async def health():
    return {"code": 0, "msg": "ok", "data": {"status": "up"}}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.APP_PORT)

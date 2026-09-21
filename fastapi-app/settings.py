"""全局配置：MySQL / PGVector / JWT / 上传目录。均可用环境变量覆盖（Docker 内通过 compose 注入）。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

APP_PORT = int(os.getenv("APP_PORT", "9090"))

# ---- MySQL 业务库 ----
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root123456")
MYSQL_DB = os.getenv("MYSQL_DB", "ai_system")

# ---- PostgreSQL + PGVector 向量库 ----
PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "root123456")
PG_DB = os.getenv("PG_DB", "vector_store")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# ---- JWT ----
JWT_SECRET = os.getenv("JWT_SECRET", "ai-system-secret-please-change")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "72"))

# ---- 百炼（DashScope）----
# 仅作为「新增模型配置」时的默认厂商地址；真正的 Key 在管理端 AI模型配置 里维护，改配置立刻生效不用重启。
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_OPENAI_BASE = os.getenv("DASHSCOPE_OPENAI_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
DASHSCOPE_NATIVE_BASE = os.getenv("DASHSCOPE_NATIVE_BASE", "https://dashscope.aliyuncs.com")
DEFAULT_VENDOR = "dashscope"

TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.mysql",
            "credentials": {
                "host": MYSQL_HOST,
                "port": str(MYSQL_PORT),
                "user": MYSQL_USER,
                "password": MYSQL_PASSWORD,
                "database": MYSQL_DB,
                "connect_timeout": 10,
            },
        }
    },
    "apps": {"models": {"models": ["models"], "default_connection": "default"}},
}

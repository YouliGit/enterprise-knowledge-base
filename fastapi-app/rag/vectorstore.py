"""PGVector 异步访问：asyncpg 直连，向量库仅 1 张表 kb_vectors。

- main.py 启动时 init_pgvector()：建连接池 + 建表（幂等，与 pgvector_init.sql 等价）
- 只对子块（或递归分块的单块）建向量，父块不参与检索（小块用来找，大块用来答）
"""
import json

import asyncpg

import settings

_pool: asyncpg.Pool | None = None


def pg_dsn() -> str:
    return (
        f"postgresql://{settings.PG_USER}:{settings.PG_PASSWORD}"
        f"@{settings.PG_HOST}:{settings.PG_PORT}/{settings.PG_DB}"
    )


async def init_pgvector(retries: int = 30, delay: float = 2.0):
    """启动时初始化：等待库可用 → 建 extension 与向量表。"""
    import asyncio

    global _pool
    last_err = None
    for _ in range(retries):
        try:
            _pool = await asyncpg.create_pool(
                pg_dsn(), min_size=1, max_size=8, command_timeout=60
            )
            break
        except Exception as e:  # 等 postgres 就绪
            last_err = e
            await asyncio.sleep(delay)
    if _pool is None:
        raise RuntimeError(f"PGVector 连接失败: {last_err}")
    async with _pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS kb_vectors (
                id          BIGSERIAL PRIMARY KEY,
                chunk_id    BIGINT UNIQUE NOT NULL,
                doc_id      BIGINT NOT NULL DEFAULT 0,
                kb_id       BIGINT NOT NULL DEFAULT 0,
                content     TEXT NOT NULL DEFAULT '',
                embedding   vector({settings.EMBEDDING_DIM}) NOT NULL,
                meta        JSONB NOT NULL DEFAULT '{{}}',
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kb_vectors_kb ON kb_vectors(kb_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kb_vectors_doc ON kb_vectors(doc_id)"
        )
    return True


async def close_pgvector():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _to_literal(vec: list[float]) -> str:
    """embedding 参数按 pgvector 字面量传入，避免需要额外扩展类型编解码"""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


async def upsert_vectors(rows: list[dict]):
    """批量写入/更新向量。row: {chunk_id, doc_id, kb_id, content, embedding, meta}"""
    if not rows:
        return
    assert _pool, "PGVector 未初始化"
    data = [
        (
            r["chunk_id"], r["doc_id"], r["kb_id"], r["content"],
            _to_literal(r["embedding"]), json.dumps(r.get("meta") or {}, ensure_ascii=False),
        )
        for r in rows
    ]
    async with _pool.acquire() as conn:
        stmt = await conn.prepare(
            """
            INSERT INTO kb_vectors (chunk_id, doc_id, kb_id, content, embedding, meta)
            VALUES ($1,$2,$3,$4,$5::vector,$6::jsonb)
            ON CONFLICT (chunk_id) DO UPDATE
            SET doc_id=EXCLUDED.doc_id, kb_id=EXCLUDED.kb_id,
                content=EXCLUDED.content, embedding=EXCLUDED.embedding, meta=EXCLUDED.meta
            """
        )
        await stmt.executemany(data)


async def delete_by_chunk_ids(chunk_ids: list[int]):
    if not chunk_ids:
        return
    assert _pool
    async with _pool.acquire() as conn:
        await conn.execute("DELETE FROM kb_vectors WHERE chunk_id = ANY($1::bigint[])", chunk_ids)


async def delete_by_doc(doc_id: int):
    assert _pool
    async with _pool.acquire() as conn:
        await conn.execute("DELETE FROM kb_vectors WHERE doc_id = $1", doc_id)


async def delete_by_kb(kb_id: int):
    assert _pool
    async with _pool.acquire() as conn:
        await conn.execute("DELETE FROM kb_vectors WHERE kb_id = $1", kb_id)


async def vector_search(kb_id: int, embedding: list[float], top_k: int = 8) -> list[dict]:
    """余弦相似度检索：score = 1 - cosine_distance，量纲 0~1。"""
    assert _pool
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT chunk_id, doc_id, content,
                   1 - (embedding <=> $2::vector) AS score
            FROM kb_vectors
            WHERE kb_id = $1
            ORDER BY embedding <=> $2::vector
            LIMIT $3
            """,
            kb_id, _to_literal(embedding), top_k,
        )
    return [
        {
            "chunk_id": r["chunk_id"],
            "doc_id": r["doc_id"],
            "content": r["content"],
            "score": float(r["score"]),
        }
        for r in rows
    ]


async def vector_count(kb_id: int | None = None) -> int:
    assert _pool
    async with _pool.acquire() as conn:
        if kb_id:
            return await conn.fetchval("SELECT count(*) FROM kb_vectors WHERE kb_id=$1", kb_id)
        return await conn.fetchval("SELECT count(*) FROM kb_vectors")

-- ============================================================
--  AI Agentic RAG 企业知识库平台 —— PostgreSQL 向量库初始化
--  数据库：PostgreSQL 16+ / PGVector，库名 vector_store（默认）
--  用法：
--    psql -U postgres -c "CREATE DATABASE vector_store;"
--    psql -U postgres -d vector_store -f pgvector_init.sql
--  与 main.py → vectorstore.init_pgvector() 的建表逻辑等价（幂等）。
--  ⚠ 需先安装 PGVector 扩展（docker 镜像 pgvector/pgvector:pg16 已内置）
-- ============================================================

-- 向量扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 向量表：全库仅此一张，只存子块（小块用来找，父块用来答，父块不入库）
CREATE TABLE IF NOT EXISTS kb_vectors (
    id         BIGSERIAL PRIMARY KEY,
    chunk_id   BIGINT UNIQUE NOT NULL,
    doc_id     BIGINT NOT NULL DEFAULT 0,
    kb_id      BIGINT NOT NULL DEFAULT 0,
    content    TEXT NOT NULL DEFAULT '',
    embedding  vector(1024) NOT NULL,          -- text-embedding-v4，1024维
    meta       JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 检索索引
CREATE INDEX IF NOT EXISTS idx_kb_vectors_kb  ON kb_vectors(kb_id);
CREATE INDEX IF NOT EXISTS idx_kb_vectors_doc ON kb_vectors(doc_id);

-- 说明：
--   1. 维度 1024 与 settings.py EMBEDDING_DIM 保持一致，如需改维度
--      需重建本表（ALTER 不能直接改 vector 维度）。
--   2. 表由后端启动时兜底创建（CREATE TABLE IF NOT EXISTS），
--      本脚本用于 Docker 初始化/手工建库场景，重复执行安全。
--   3. 相似度检索用余弦距离（<=>），score = 1 - cosine_distance，量纲 0~1，
--      与 rag/vectorstore.py 中 vector_search 的写法一致。
-- ============================================================
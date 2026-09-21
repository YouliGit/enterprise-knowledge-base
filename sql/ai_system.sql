-- ============================================================
--  AI Agentic RAG 企业知识库平台 —— MySQL 业务库（25 张表）
--  数据库：MySQL 8，库名 ai_system（默认，可被环境变量 MYSQL_DB 覆盖）
--  用法：  mysql -uroot -p < ai_system.sql
--  ⚠ 种子数据（admin/admin、默认切分/检索策略）由后端 main.py 首启
--     ensure_seed_data() 自动创建，本文件只负责表结构。
--  与 ai_system/fastapi-app/models.py 的 Tortoise 模型一一对应。
-- ============================================================

CREATE DATABASE IF NOT EXISTS ai_system
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ai_system;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. 用户 user
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id`          INT NOT NULL AUTO_INCREMENT,
  `username`    VARCHAR(64)  NOT NULL,
  `password`    VARCHAR(256) NOT NULL COMMENT '密码哈希 pbkdf2_sha256',
  `nickname`    VARCHAR(64)  NOT NULL DEFAULT '',
  `avatar`      VARCHAR(512) NOT NULL DEFAULT '',
  `email`       VARCHAR(128) NOT NULL DEFAULT '',
  `phone`       VARCHAR(32)  NOT NULL DEFAULT '',
  `role`        VARCHAR(16)  NOT NULL DEFAULT 'user' COMMENT 'admin/user',
  `status`      INT          NOT NULL DEFAULT 1 COMMENT '1启用 0禁用',
  `created_at`  DATETIME(6)  NULL,
  `updated_at`  DATETIME(6)  NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户';

-- ------------------------------------------------------------
-- 2. AI模型配置 ai_model_config
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `ai_model_config`;
CREATE TABLE `ai_model_config` (
  `id`          INT NOT NULL AUTO_INCREMENT,
  `name`        VARCHAR(128) NOT NULL COMMENT '配置名称',
  `type`        VARCHAR(16)  NOT NULL COMMENT 'chat/embedding/rerank',
  `model`       VARCHAR(128) NOT NULL COMMENT '模型名',
  `vendor`      VARCHAR(32)  NOT NULL DEFAULT 'dashscope',
  `api_base`    VARCHAR(512) NOT NULL DEFAULT '' COMMENT '留空自动用百炼兼容地址',
  `api_key`     VARCHAR(512) NOT NULL DEFAULT '' COMMENT 'API Key',
  `dimension`   INT          NOT NULL DEFAULT 0 COMMENT '向量维度，仅向量模型',
  `temperature` DOUBLE       NOT NULL DEFAULT 0.7 COMMENT '温度，仅对话模型',
  `enabled`     INT          NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
  `remark`      VARCHAR(512) NOT NULL DEFAULT '',
  `test_info`   VARCHAR(512) NOT NULL DEFAULT '' COMMENT '最近一次连通性测试结果',
  `created_at`  DATETIME(6)  NULL,
  `updated_at`  DATETIME(6)  NULL,
  PRIMARY KEY (`id`),
  KEY `idx_model_type` (`type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI模型配置';

-- ------------------------------------------------------------
-- 3. Prompt模板 prompt_template
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `prompt_template`;
CREATE TABLE `prompt_template` (
  `id`         INT NOT NULL AUTO_INCREMENT,
  `code`       VARCHAR(64)  NOT NULL,
  `name`       VARCHAR(128) NOT NULL,
  `scene`      VARCHAR(32)  NOT NULL COMMENT 'qa问答/rewrite改写/agent智能体/judge评测',
  `content`    LONGTEXT     NOT NULL COMMENT '内容，支持 {variable} 占位符',
  `enabled`    INT          NOT NULL DEFAULT 1,
  `remark`     VARCHAR(512) NOT NULL DEFAULT '',
  `created_at` DATETIME(6)  NULL,
  `updated_at` DATETIME(6)  NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_prompt_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Prompt模板';

-- ------------------------------------------------------------
-- 4. 工具 tool
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `tool`;
CREATE TABLE `tool` (
  `id`          INT NOT NULL AUTO_INCREMENT,
  `code`        VARCHAR(64)  NOT NULL,
  `name`        VARCHAR(128) NOT NULL,
  `description` LONGTEXT     NOT NULL COMMENT '给模型看的工具说明',
  `schema_json` LONGTEXT     NOT NULL COMMENT 'Function Calling JSON Schema',
  `handler`     VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '内置处理器名',
  `built_in`    INT          NOT NULL DEFAULT 0 COMMENT '1内置',
  `enabled`     INT          NOT NULL DEFAULT 1,
  `created_at`  DATETIME(6)  NULL,
  `updated_at`  DATETIME(6)  NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_tool_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工具';

-- ------------------------------------------------------------
-- 5. 工具调用日志 tool_call_log
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `tool_call_log`;
CREATE TABLE `tool_call_log` (
  `id`           INT NOT NULL AUTO_INCREMENT,
  `tool_id`      BIGINT       NULL,
  `tool_code`    VARCHAR(64)  NOT NULL DEFAULT '',
  `agent_run_id` BIGINT       NULL COMMENT '关联Agent运行',
  `args_json`    LONGTEXT     NOT NULL,
  `result`       LONGTEXT     NOT NULL,
  `status`       VARCHAR(16)  NOT NULL DEFAULT 'ok' COMMENT 'ok/failed',
  `cost_ms`      INT          NOT NULL DEFAULT 0,
  `created_at`   DATETIME(6)  NULL,
  `updated_at`   DATETIME(6)  NULL,
  PRIMARY KEY (`id`),
  KEY `idx_tcl_code` (`tool_code`),
  KEY `idx_tcl_run` (`agent_run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工具调用日志';

-- ------------------------------------------------------------
-- 6. 知识库 knowledge_base
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `knowledge_base`;
CREATE TABLE `knowledge_base` (
  `id`                    INT NOT NULL AUTO_INCREMENT,
  `name`                  VARCHAR(128) NOT NULL,
  `description`           LONGTEXT     NOT NULL,
  `vector_model_id`       BIGINT       NULL COMMENT '绑定的向量模型配置',
  `split_strategy_id`     BIGINT       NULL COMMENT '绑定的切分策略',
  `retrieval_strategy_id` BIGINT       NULL COMMENT '默认检索策略',
  `owner_id`              BIGINT       NULL,
  `status`                INT          NOT NULL DEFAULT 1,
  `created_at`            DATETIME(6)  NULL,
  `updated_at`            DATETIME(6)  NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库';

-- ------------------------------------------------------------
-- 7. 切分策略 split_strategy
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `split_strategy`;
CREATE TABLE `split_strategy` (
  `id`                  INT NOT NULL AUTO_INCREMENT,
  `name`                VARCHAR(128) NOT NULL,
  `mode`                VARCHAR(16)  NOT NULL DEFAULT 'parent_child' COMMENT 'recursive/parent_child',
  `chunk_size`          INT          NOT NULL DEFAULT 500 COMMENT '子块大小(字符)',
  `chunk_overlap`       INT          NOT NULL DEFAULT 50,
  `parent_chunk_size`   INT          NOT NULL DEFAULT 1500 COMMENT '父块大小，父子分块时生效',
  `parent_chunk_overlap` INT         NOT NULL DEFAULT 100,
  `separators_json`     LONGTEXT     NOT NULL COMMENT '递归分隔符',
  `remark`              VARCHAR(512) NOT NULL DEFAULT '',
  `created_at`          DATETIME(6)  NULL,
  `updated_at`          DATETIME(6)  NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='切分策略';

-- ------------------------------------------------------------
-- 8. 检索策略 retrieval_strategy
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `retrieval_strategy`;
CREATE TABLE `retrieval_strategy` (
  `id`               INT NOT NULL AUTO_INCREMENT,
  `name`             VARCHAR(128) NOT NULL,
  `description`      VARCHAR(512) NOT NULL DEFAULT '',
  `vector_top_k`     INT          NOT NULL DEFAULT 8 COMMENT '向量召回数',
  `bm25_top_k`       INT          NOT NULL DEFAULT 8 COMMENT 'BM25召回数，0为关闭',
  `rrf_k`            INT          NOT NULL DEFAULT 60 COMMENT 'RRF 常数k',
  `use_rewrite`      INT          NOT NULL DEFAULT 1 COMMENT '是否启用查询改写',
  `rewrite_mode`     VARCHAR(16)  NOT NULL DEFAULT 'multi_query' COMMENT 'multi_query/hyde/coref',
  `candidate_limit`  INT          NOT NULL DEFAULT 20 COMMENT '重排候选上限',
  `cosine_threshold` DOUBLE       NOT NULL DEFAULT 0.30 COMMENT '余弦相似度阈值(量纲0~1)',
  `rerank_enabled`   INT          NOT NULL DEFAULT 1,
  `rerank_top_n`     INT          NOT NULL DEFAULT 5 COMMENT '重排后保留数',
  `rerank_threshold` DOUBLE       NOT NULL DEFAULT 0.05 COMMENT '重排相关分阈值(量纲0~1)',
  `max_retrieval`    INT          NOT NULL DEFAULT 2 COMMENT 'Agent 最大检索轮次上限',
  `created_at`       DATETIME(6)  NULL,
  `updated_at`       DATETIME(6)  NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='检索策略';

-- ------------------------------------------------------------
-- 9. 文档 document
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `document`;
CREATE TABLE `document` (
  `id`          INT NOT NULL AUTO_INCREMENT,
  `kb_id`       BIGINT       NOT NULL,
  `name`        VARCHAR(256) NOT NULL,
  `file_type`   VARCHAR(16)  NOT NULL DEFAULT '' COMMENT 'pdf/docx/xlsx/md/txt',
  `file_size`   BIGINT       NOT NULL DEFAULT 0,
  `file_path`   VARCHAR(512) NOT NULL DEFAULT '',
  `status`      VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending/parsing/parsed/failed',
  `chunk_count` INT          NOT NULL DEFAULT 0,
  `error`       LONGTEXT     NOT NULL,
  `created_at`  DATETIME(6)  NULL,
  `updated_at`  DATETIME(6)  NULL,
  PRIMARY KEY (`id`),
  KEY `idx_doc_kb` (`kb_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档';

-- ------------------------------------------------------------
-- 10. 片段 chunk
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `chunk`;
CREATE TABLE `chunk` (
  `id`        INT NOT NULL AUTO_INCREMENT,
  `doc_id`    BIGINT   NOT NULL,
  `kb_id`     BIGINT   NOT NULL,
  `parent_id` BIGINT   NULL COMMENT '父块ID，父子分块时子块指向父块',
  `seq`       INT      NOT NULL DEFAULT 0,
  `content`   LONGTEXT NOT NULL,
  `char_len`  INT      NOT NULL DEFAULT 0,
  `is_parent` INT      NOT NULL DEFAULT 0 COMMENT '1父块 0子块',
  `enabled`   INT      NOT NULL DEFAULT 1 COMMENT '人工修正可禁用某片段',
  `meta_json` LONGTEXT NOT NULL,
  `created_at` DATETIME(6) NULL,
  `updated_at` DATETIME(6) NULL,
  PRIMARY KEY (`id`),
  KEY `idx_chunk_doc` (`doc_id`),
  KEY `idx_chunk_kb` (`kb_id`),
  KEY `idx_chunk_parent` (`parent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='片段';

-- ------------------------------------------------------------
-- 11. 检索测试日志 retrieval_test_log
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `retrieval_test_log`;
CREATE TABLE `retrieval_test_log` (
  `id`          INT NOT NULL AUTO_INCREMENT,
  `kb_id`       BIGINT   NOT NULL,
  `query`       LONGTEXT NOT NULL,
  `strategy_id` BIGINT   NULL,
  `result_json` LONGTEXT NOT NULL,
  `cost_ms`     INT      NOT NULL DEFAULT 0,
  `user_id`     BIGINT   NULL,
  `created_at`  DATETIME(6) NULL,
  `updated_at`  DATETIME(6) NULL,
  PRIMARY KEY (`id`),
  KEY `idx_rtl_kb` (`kb_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='检索测试日志';

-- ------------------------------------------------------------
-- 12. 问答应用 chat_app
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `chat_app`;
CREATE TABLE `chat_app` (
  `id`                    INT NOT NULL AUTO_INCREMENT,
  `name`                  VARCHAR(128) NOT NULL,
  `description`           LONGTEXT     NOT NULL,
  `owner_id`              BIGINT       NULL,
  `prompt_template_id`    BIGINT       NULL COMMENT '问答Prompt模板',
  `model_config_id`       BIGINT       NULL COMMENT '对话模型配置',
  `retrieval_strategy_id` BIGINT       NULL,
  `max_history`           INT          NOT NULL DEFAULT 3 COMMENT '携带历史轮数',
  `show_ref`              INT          NOT NULL DEFAULT 1 COMMENT '是否展示引用来源',
  `use_agent`             INT          NOT NULL DEFAULT 1 COMMENT '1走Agentic RAG状态图 0走单轮混合检索',
  `enabled`               INT          NOT NULL DEFAULT 1,
  `created_at`            DATETIME(6)  NULL,
  `updated_at`            DATETIME(6)  NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='问答应用';

-- ------------------------------------------------------------
-- 13. 应用-知识库关联 app_kb_rel
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `app_kb_rel`;
CREATE TABLE `app_kb_rel` (
  `id`         INT NOT NULL AUTO_INCREMENT,
  `app_id`     BIGINT NOT NULL,
  `kb_id`      BIGINT NOT NULL,
  `created_at` DATETIME(6) NULL,
  `updated_at` DATETIME(6) NULL,
  PRIMARY KEY (`id`),
  KEY `idx_akr_app` (`app_id`),
  KEY `idx_akr_kb` (`kb_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='应用-知识库关联';

-- ------------------------------------------------------------
-- 14. 会话 chat_session
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `chat_session`;
CREATE TABLE `chat_session` (
  `id`         INT NOT NULL AUTO_INCREMENT,
  `app_id`     BIGINT       NOT NULL,
  `user_id`    BIGINT       NOT NULL,
  `title`      VARCHAR(128) NOT NULL DEFAULT '新会话',
  `msg_count`  INT          NOT NULL DEFAULT 0,
  `created_at` DATETIME(6)  NULL,
  `updated_at` DATETIME(6)  NULL,
  PRIMARY KEY (`id`),
  KEY `idx_cs_app` (`app_id`),
  KEY `idx_cs_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话';

-- ------------------------------------------------------------
-- 15. 消息 chat_message
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `chat_message`;
CREATE TABLE `chat_message` (
  `id`           INT NOT NULL AUTO_INCREMENT,
  `session_id`   BIGINT       NOT NULL,
  `app_id`       BIGINT       NOT NULL DEFAULT 0,
  `user_id`      BIGINT       NOT NULL DEFAULT 0,
  `role`         VARCHAR(16)  NOT NULL COMMENT 'user/assistant',
  `content`      LONGTEXT     NOT NULL,
  `refs_json`    LONGTEXT     NOT NULL COMMENT '引用来源片段',
  `feedback`     VARCHAR(16)  NOT NULL DEFAULT '' COMMENT 'useful/useless/空',
  `cost_ms`      INT          NOT NULL DEFAULT 0,
  `agent_run_id` BIGINT       NULL,
  `created_at`   DATETIME(6)  NULL,
  `updated_at`   DATETIME(6)  NULL,
  PRIMARY KEY (`id`),
  KEY `idx_cm_session` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息';

-- ------------------------------------------------------------
-- 16. Agent运行 agent_run
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `agent_run`;
CREATE TABLE `agent_run` (
  `id`            INT NOT NULL AUTO_INCREMENT,
  `app_id`        BIGINT   NOT NULL DEFAULT 0,
  `session_id`    BIGINT   NOT NULL DEFAULT 0,
  `user_id`       BIGINT   NOT NULL DEFAULT 0,
  `query`         LONGTEXT NOT NULL,
  `status`        VARCHAR(16) NOT NULL DEFAULT 'running' COMMENT 'running/done/failed',
  `rounds`        INT      NOT NULL DEFAULT 0 COMMENT '实际检索轮次',
  `final_answer`  LONGTEXT NOT NULL,
  `total_cost_ms` INT      NOT NULL DEFAULT 0,
  `created_at`    DATETIME(6) NULL,
  `updated_at`    DATETIME(6) NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent运行';

-- ------------------------------------------------------------
-- 17. Agent步骤 agent_step（时间线回放）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `agent_step`;
CREATE TABLE `agent_step` (
  `id`         INT NOT NULL AUTO_INCREMENT,
  `run_id`     BIGINT       NOT NULL,
  `seq`        INT          NOT NULL DEFAULT 0,
  `node`       VARCHAR(32)  NOT NULL COMMENT 'retrieve/evaluate/rewrite/generate/self_check/tool',
  `action`     VARCHAR(128) NOT NULL DEFAULT '',
  `thought`    LONGTEXT     NOT NULL COMMENT '模型判断理由',
  `input_json` LONGTEXT     NOT NULL,
  `output_json` LONGTEXT    NOT NULL,
  `status`     VARCHAR(16)  NOT NULL DEFAULT 'ok',
  `cost_ms`    INT          NOT NULL DEFAULT 0,
  `created_at` DATETIME(6)  NULL,
  `updated_at` DATETIME(6)  NULL,
  PRIMARY KEY (`id`),
  KEY `idx_as_run` (`run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent步骤';

-- ------------------------------------------------------------
-- 18. 评测集 eval_dataset
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `eval_dataset`;
CREATE TABLE `eval_dataset` (
  `id`          INT NOT NULL AUTO_INCREMENT,
  `name`        VARCHAR(128) NOT NULL,
  `description` LONGTEXT     NOT NULL,
  `kb_id`       BIGINT       NULL,
  `owner_id`    BIGINT       NULL,
  `created_at`  DATETIME(6)  NULL,
  `updated_at`  DATETIME(6)  NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评测集';

-- ------------------------------------------------------------
-- 19. 评测用例 eval_case
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `eval_case`;
CREATE TABLE `eval_case` (
  `id`                   INT NOT NULL AUTO_INCREMENT,
  `dataset_id`           BIGINT   NOT NULL,
  `question`             LONGTEXT NOT NULL,
  `ground_truth`         LONGTEXT NOT NULL COMMENT '参考答案',
  `source_chunk_ids_json` LONGTEXT NOT NULL COMMENT '来源片段ID，Context Recall做集合运算',
  `created_at`           DATETIME(6) NULL,
  `updated_at`           DATETIME(6) NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ec_dataset` (`dataset_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评测用例';

-- ------------------------------------------------------------
-- 20. 评测运行 eval_run
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `eval_run`;
CREATE TABLE `eval_run` (
  `id`           INT NOT NULL AUTO_INCREMENT,
  `dataset_id`   BIGINT     NOT NULL,
  `kb_id`        BIGINT     NOT NULL,
  `strategy_id`  BIGINT     NULL,
  `report_name`  VARCHAR(128) NOT NULL DEFAULT '评测报告',
  `status`       VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/done/failed',
  `case_count`   INT        NOT NULL DEFAULT 0,
  `recall`       DOUBLE     NOT NULL DEFAULT 0 COMMENT 'Context Recall',
  `precision`    DOUBLE     NOT NULL DEFAULT 0 COMMENT 'Context Precision',
  `faithfulness` DOUBLE     NOT NULL DEFAULT 0 COMMENT 'Faithfulness',
  `relevancy`    DOUBLE     NOT NULL DEFAULT 0 COMMENT 'Answer Relevancy',
  `overall`      DOUBLE     NOT NULL DEFAULT 0 COMMENT '综合分',
  `error`        LONGTEXT   NOT NULL,
  `created_at`   DATETIME(6) NULL,
  `updated_at`   DATETIME(6) NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评测运行';

-- ------------------------------------------------------------
-- 21. 评测运行明细 eval_run_item
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `eval_run_item`;
CREATE TABLE `eval_run_item` (
  `id`              INT NOT NULL AUTO_INCREMENT,
  `run_id`          BIGINT   NOT NULL,
  `case_id`         BIGINT   NOT NULL,
  `question`        LONGTEXT NOT NULL,
  `contexts_json`   LONGTEXT NOT NULL COMMENT '召回上下文',
  `context_ids_json` LONGTEXT NOT NULL,
  `answer`          LONGTEXT NOT NULL,
  `recall`          DOUBLE   NOT NULL DEFAULT 0,
  `precision`       DOUBLE   NOT NULL DEFAULT 0,
  `faithfulness`    DOUBLE   NOT NULL DEFAULT 0,
  `relevancy`       DOUBLE   NOT NULL DEFAULT 0,
  `overall`         DOUBLE   NOT NULL DEFAULT 0,
  `detail_json`     LONGTEXT NOT NULL,
  `created_at`      DATETIME(6) NULL,
  `updated_at`      DATETIME(6) NULL,
  PRIMARY KEY (`id`),
  KEY `idx_eri_run` (`run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='评测运行明细';

-- ------------------------------------------------------------
-- 22. 策略对比运行 compare_run
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `compare_run`;
CREATE TABLE `compare_run` (
  `id`          INT NOT NULL AUTO_INCREMENT,
  `name`        VARCHAR(128) NOT NULL DEFAULT '策略对比',
  `kb_id`       BIGINT   NOT NULL,
  `dataset_id`  BIGINT   NOT NULL,
  `status`      VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/done/failed',
  `arm_count`   INT      NOT NULL DEFAULT 0,
  `error`       LONGTEXT NOT NULL,
  `created_at`  DATETIME(6) NULL,
  `updated_at`  DATETIME(6) NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='策略对比运行';

-- ------------------------------------------------------------
-- 23. 策略对比臂 compare_arm
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `compare_arm`;
CREATE TABLE `compare_arm` (
  `id`            INT NOT NULL AUTO_INCREMENT,
  `run_id`        BIGINT       NOT NULL,
  `arm_index`     INT          NOT NULL DEFAULT 0 COMMENT '0~3，最多4套并排',
  `strategy_id`   BIGINT       NULL,
  `strategy_name` VARCHAR(128) NOT NULL DEFAULT '',
  `recall`        DOUBLE       NOT NULL DEFAULT 0,
  `precision`     DOUBLE       NOT NULL DEFAULT 0,
  `faithfulness`  DOUBLE       NOT NULL DEFAULT 0,
  `relevancy`     DOUBLE       NOT NULL DEFAULT 0,
  `overall`       DOUBLE       NOT NULL DEFAULT 0,
  `avg_cost_ms`   INT          NOT NULL DEFAULT 0,
  `created_at`    DATETIME(6)  NULL,
  `updated_at`    DATETIME(6)  NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ca_run` (`run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='策略对比臂';

-- ------------------------------------------------------------
-- 24. 操作日志 operation_log
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `operation_log`;
CREATE TABLE `operation_log` (
  `id`         INT NOT NULL AUTO_INCREMENT,
  `user_id`    BIGINT       NULL,
  `username`   VARCHAR(64)  NOT NULL DEFAULT '',
  `action`     VARCHAR(128) NOT NULL DEFAULT '',
  `detail`     LONGTEXT     NOT NULL,
  `ip`         VARCHAR(64)  NOT NULL DEFAULT '',
  `created_at` DATETIME(6)  NULL,
  `updated_at` DATETIME(6)  NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ol_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作日志';

-- ------------------------------------------------------------
-- 25. 系统配置 sys_config
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `sys_config`;
CREATE TABLE `sys_config` (
  `id`         INT NOT NULL AUTO_INCREMENT,
  `key`        VARCHAR(64) NOT NULL,
  `value`      LONGTEXT    NOT NULL,
  `remark`     VARCHAR(256) NOT NULL DEFAULT '',
  `created_at` DATETIME(6) NULL,
  `updated_at` DATETIME(6) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sc_key` (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置';

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- 种子数据说明（不需要手写）：
--   admin/admin 账号、默认切分策略2条、默认检索策略3条
--   由后端 main.py 的 ensure_seed_data() 首次启动自动创建（幂等）。
-- ------------------------------------------------------------
# 材料 5 · 技术使用记录

本次任务中三项技术都实际参与了流程。下面给出每类记录的**位置**与**复现方式**。

---

## 1. MiniMax 开发记录

| 项 | 值 |
| --- | --- |
| 记录文件 | `../transcript/minimax_session.jsonl`（每行一条 JSON） |
| 录制脚本 | `../scripts/record_session.py --live` |
| 模型 | 由 `MINIMAX_MODEL` 指定，默认 `MiniMax-M2` |
| 接口 | 由 `MINIMAX_BASE_URL` 指定，默认 `https://api.minimaxi.com/v1` |

每条记录包含：

| 字段 | 含义 |
| --- | --- |
| `ts` | 时间戳（UTC，ISO 8601） |
| `role` | `user` / `assistant` |
| `provider` | 固定为 `minimax` |
| `mode` | `live` 表示真实调用；`bootstrap` 表示离线引导记录 |
| `model` | 使用的模型名 |
| `task_id` | 任务编号 |
| `task` | 本次任务描述 |
| `context_digest` | **当时实际交给模型的上下文摘要**（sha256） |
| `context_sources` | 当时上下文中每一条来源（规格 / 代码 / 测试的文件名） |
| `applied_files` | 模型改动���文件 |
| `diff_sha256` | 模型产出补丁的 sha256 |
| `content` | 实际发送给模型的任务文本 / 模型返回的内容 |

门禁 2 会校验：`context_digest` 与当前模块组装出的上下文摘要一致、
`context_sources` 与当前选材结果一致、`diff_sha256` 与 `../transcript/feature.patch` 一致、
`applied_files` 与补丁实际改动的文件一致。

**随包提交的记录**：`../transcript/minimax_session.jsonl`（原始开发记录）与
`../artifacts/usage/minimax-usage.json`（同一份记录的字段汇总，由 `python scripts/dump_usage.py` 生成）。

> **提交前必须用你自己的 MiniMax 账号重新录制**：
> ```bash
> export MINIMAX_API_KEY=<你的 Key>
> python scripts/record_session.py --live
> ```
> 随仓库提供的是 `mode: "bootstrap"` 的离线引导记录，仅用于让自测可以离线跑通。

---

## 2. 数据库（seekdb）查询记录

| 项 | 值 |
| --- | --- |
| 存储引擎 | 嵌入式 seekdb（`pylibseekdb`），无需另行部署数据库服务 |
| 数据目录 | `minimax/.ctxmodule-data/seekdb`（可用 `CTXMODULE_SEEKDB_DIR` 指定） |
| 表 | `ctx_documents(doc_id, kind, path, title, content, spec_ids, source_hash, updated_at)` |

模块实际执行的 SQL：

```sql
-- 写入（每份材料一行）
DELETE FROM ctx_documents WHERE doc_id = '<doc_id>';
INSERT INTO ctx_documents
  (doc_id, kind, path, title, content, spec_ids, source_hash, updated_at)
VALUES ('<doc_id>', '<kind>', '<path>', '<title>', '<content>', '<spec_ids>', '<hash>', '<hash>');

-- 选材（真实检索，任务词逐个 AND 匹配）
SELECT doc_id, kind, path, title, content, spec_ids, source_hash
FROM ctx_documents
WHERE content LIKE '%filter%'
  AND content LIKE '%status%'
  AND content LIKE '%records%'
  AND content LIKE '%billing%'
ORDER BY doc_id
LIMIT 50;

-- 回查某一条来源
SELECT doc_id, kind, path, title, content, spec_ids, source_hash
FROM ctx_documents WHERE doc_id = 'code:src/billing/filter.py';
```

门禁 4 会验证：上下文中的每一条代码 / 测试来源都能在数据库行中**逐字回查**，
且检索结果由查询驱动（无关词返回空集）。

**随包提交的记录**：`../artifacts/usage/seekdb-queries.txt`——记录了数据库目录、表名、
文档总数、检索命中的每一行（`doc_id / kind / path / source_hash`）以及最终进入上下文的来源清单。

查看实际数据：

```bash
python - <<'PY'
from ctxmodule.seekdb_store import SeekDBStore
store = SeekDBStore(".ctxmodule-data/seekdb").open()
for doc in store.all_documents():
    print(doc.kind, doc.path, doc.source_hash[:12])
PY
```

---

## 3. PowerContext 状态写入与复用记录

| 项 | 值 |
| --- | --- |
| 接入方式 | 官方 HTTP API（`/v1/scopes`、`/v1/sources/content`、`/v1/memory/remember`、`/v1/context/prepare`） |
| 持久化 | PowerContext Server 自身的 SQLite（`POWERCONTEXT_HOME` 目录） |
| 写入位置 | `ctxmodule/pc.py` 的 `save_task_state()` |
| 读回位置 | `ctxmodule/pc.py` 的 `load_task_state()` |

写入的调用序列：

```
POST /v1/scopes             {"scope_id": "<idempotency key>", ...}
POST /v1/sources/content    {"scope_id": ..., "source_id": "task-state:<task_id>", "content": "<状态 JSON>"}
POST /v1/memory/remember    {"scope_id": ..., "kind": "decision", "text": "<状态摘要>", "reason": "..."}
POST /v1/context/prepare    {"scope_id": ..., "query": "task state <task_id>", "max_bytes": 16384}
```

**复用验证**：门禁 5 会启动真实的 PowerContext Server → 从空状态写入任务记录 →
**结束该 Server 进程并用同一 `POWERCONTEXT_HOME` 重新启动** → 再次读取状态并用于后续处理。
这证明状态保存在 PowerContext 的持久化存储里，而不是进程内存。

**随包提交的记录**：`../artifacts/usage/powercontext-state.txt`——由
`python scripts/dump_usage.py` 生成，完整记录了这次**写入 → 重启 → 读回**的全过程：
Server 启动命令、`POWERCONTEXT_HOME`、scope 标题与幂等键、写入的状态 JSON、
重启后读回的状态 JSON，以及用读回的状态重新 `prepare_context` 得到的上下文。

复现：

```bash
export CTXMODULE_HTTP_LOG=artifacts/powercontext-calls.jsonl
python -m ctxmodule state --task-id TASK-BILL-001
cat artifacts/powercontext-calls.jsonl

# 重新生成上面那份记录
python scripts/dump_usage.py
```

> HTTP 日志只记录请求路径、payload 的键名与响应状态码，**不记录任何凭据**。

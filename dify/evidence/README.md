# 证据索引与核验方法

本目录记录 2026-11-05 在真实 Dify 1.9.1 + PowerContext 1.2.0（SeekDB）上的运行结果。
所有文件均可与本仓库的 `app.yml` 对上；没有记录任何 token / API key。

## 文件

| 文件 | 内容 |
| --- | --- |
| `scenario_run.json` | 用户 `nightshift-demo-04` 的五轮对话：请求、回答、耗时、`conversation_id`、`message_id`、`workflow_run_id`、节点级执行（状态/耗时/输出）、账本前后快照 |
| `ledger_dump.json` | 该用户 scope `scp_2m173y9qn52aep9xf4ggky4g1e` 的完整账本（3 条） |
| `ui-chat-prank.png` | WebApp 恶作剧回合：回答、行动选项、状态行 |
| `ui-recall-new-conversation.png` | 新建对话后翻旧账：答出“价目表画了两撇胡子” |
| `ui-workflow-process.png` | 单轮运行详情：节点名、状态、耗时（含 HTTP 节点） |

## 怎么核对

### 1. 看跨会话记忆

```bash
python -c "
import json
d=json.load(open('evidence/scenario_run.json',encoding='utf-8'))
for t in d['turns']:
    print(t['label'], t['conversation_id'][:8], t['workflow_run_id'][:8], t['elapsed_s'], 's')
print('scope:', d['scope_id'])
print('A/B conversations differ:', d['conversations']['A'] != d['conversations']['B'])
"
```

B1 的 `node_trace` 中：

- `http_scope.outputs.status_code == 201`，`scope_id` 与 `ledger_dump.json` 一致；
- `http_ledger.outputs.status_code == 200`，`entry_count == 3`，`entries` 含 A1 的 prank 条目；
- `code_ledger.outputs.intent == "recall"`，`npc_name == "小笼包"`；
- `if_write` 选择 `false`，`if_route` 选择 `true`；
- `answer_recall.outputs.answer` 含“价目表画了两撇胡子”。

### 2. 看节点级记录来源

`workflow_run_id` 与 `node_trace` 来自 Dify 自己的数据库：

```bash
docker exec dify-deploy-db-1 psql -U postgres -d dify -At -c \
  "select workflow_run_id, node_id, status, round(elapsed_time*1000)::int
   from workflow_node_executions
   where workflow_run_id='84baf69c-4342-44ba-93a2-026a32ccf037'
   order by index;"
```

这不是自写模拟器；同一条 SQL 可以在评审自己的 Dify 实例上执行。

### 3. 看账本

```bash
python scripts/inspect_memory.py --user nightshift-demo-04 \
  --token "$POWERCONTEXT_CLIENT_API_TOKEN"
```

或直接看 `ledger_dump.json`。账本里 `gift`/`prank` 条目的 `say` 字段就是 A1/A2 的玩家原话，
`npc-name` 条目就是 A3 的新名字。

### 4. 看截图

三张 PNG 为 2026-11-05 在 `http://127.0.0.1:8088/chat/...` 的 WebApp 实际操作截图，
未做内容拼接；状态行、旧事引用与运行节点面板都可见。

## 后端与版本核验

```bash
curl -s http://127.0.0.1:8000/health/ready
```

实测：

```json
{"status":"ready","checks":{"runtime":"ready","database":"ready",
 "access_mode":"enforced","authentication_provider":"ready",
 "access_provider":"ready","access_resource_kinds":"server,scope,artifact"}}
```

```bash
docker exec pc-server sh -c 'echo $POWERCONTEXT_SERVER_DATABASE_KIND; powercontext --version'
```

实测输出：

```
seekdb
1.2.0
```

容器内 `/data/seekdb` 含 `etc/ log/ run/ store/`，即数据落在 SeekDB 目录，而不是 SQLite 单文件。

## 复跑

见 `../README.md` 4.5 与 `../scripts/run_scenario.py`。注意：

- 复跑请使用新的 `--user`（或新的隐身窗口），否则会复用已有 scope，状态不归零；
- `DIFY_APP_ID` 仅用于抓节点级记录；不提供时脚本仍会记录 API 层回答与账本；
- 截图需要在浏览器里手动操作，脚本不生成截图。

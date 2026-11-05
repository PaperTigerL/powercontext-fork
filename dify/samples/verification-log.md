# 实测记录 · 2026-11-05

本文件记录**真实运行**（不是期望值）。原始机器可读记录见
[`../evidence/scenario_run.json`](../evidence/scenario_run.json)，截图见 [`../evidence/`](../evidence/)。

## 1. 环境

| 项目 | 值 |
| --- | --- |
| 宿主机 | Windows 11 10.0.26300，Docker Desktop（WSL2） |
| Dify | `langgenius/dify-api:1.9.1`、`langgenius/dify-web:1.9.1`、plugin_daemon 0.3.0-local、PostgreSQL 15、Redis 6、sandbox 0.2.12、ssrf_proxy、weaviate 1.19.0、nginx |
| Dify 入口 | `http://127.0.0.1:8088`（`EXPOSE_NGINX_PORT=8088`） |
| 模型 | Qwen2.5-3B-Instruct Q4_K_M，`llama-cpp-python[server]`，`http://127.0.0.1:11435/v1`，别名 `qwen2.5-3b-instruct`，ctx 4096 |
| 模型插件 | `langgenius/openai_api_compatible:0.0.73`（本地 difypkg 离线安装） |
| PowerContext | `powercontext[cli,server,seekdb]==1.2.0`，容器 `pc-server` |
| PowerContext 后端 | `POWERCONTEXT_SERVER_DATABASE_KIND=seekdb`，`/data/seekdb` |
| 鉴权 | `ACCESS_MODE=enforced`，Bearer token |
| 时间 | 2026-11-05 |

## 2. PowerContext 就绪与后端核验

```bash
curl -s http://127.0.0.1:8000/health/ready
```

```json
{"status":"ready","checks":{"runtime":"ready","database":"ready",
 "access_mode":"enforced","authentication_provider":"ready",
 "access_provider":"ready","access_resource_kinds":"server,scope,artifact"}}
```

```bash
docker exec pc-server sh -c 'echo $POWERCONTEXT_SERVER_DATABASE_KIND; powercontext --version; ls -la /data/seekdb'
```

```
seekdb
1.2.0
/data/seekdb: etc  log  run  store
```

结论：服务为 1.2.0，后端是 SeekDB（非 SQLite），鉴权已开启，健康检查 ready。

## 3. DSL 在真实 Dify 中的导入与发布

- 通过 Dify 控制台导入 `app.yml`（DSL `version: 0.1.5`，模式 `advanced-chat`），
  导入后为 15 节点 / 15 边；
- 在应用环境变量中填入 `PC_BASE_URL=http://host.docker.internal:8000` 与真实 token；
- 保存草稿并发布（工作流版本记录出现发布行，应用状态 normal）；
- 创建应用 API key 用于脚本验证。

## 4. 五轮端到端运行

用户 `nightshift-demo-04`（全新，运行前无 scope），通过 Dify App API（`POST /v1/chat-messages`，
`user=nightshift-demo-04`）运行；会话 A 一个 conversation，会话 B 新建一个 conversation。

| 轮次 | 输入 | HTTP | 耗时 | workflow_run_id |
| --- | --- | --- | --- | --- |
| A1 恶作剧 | 我把货架上的布丁按颜色排成彩虹了，还给价目表画了两撇胡子。 | 200 | 20.8 s | `32ab4822-fec3-4438-94bb-1e55ce759a7d` |
| A2 示好 | 给你带了根猫条，还有热豆浆。 | 200 | 9.9 s | `f193d014-0aa0-4caa-bfe2-dcce18b22cef` |
| A3 改名 | 以后你就叫小笼包吧。 | 200 | 12.4 s | `63c2490d-0e88-47d9-8c0e-96ba632cbb19` |
| B1 翻旧账 | 你还记得我上次干了什么吗？ | 200 | 19.3 s | `84baf69c-4342-44ba-93a2-026a32ccf037` |
| B2 闲聊 | 我今天有点困，站了一天。 | 200 | 9.7 s | `fefa312f-0f17-4f42-aa8f-662ff96c11b9` |

状态行：

```
A1  【小本子】好感 -1｜记仇 2｜已记 1 件事｜NPC：团子
A2  【小本子】好感 1｜记仇 2｜已记 2 件事｜NPC：团子
A3  【小本子】好感 1｜记仇 2｜已记 2 件事｜NPC：小笼包
B1  【小本子】好感 1｜记仇 2｜已记 2 件事｜NPC：小笼包
B2  【小本子】好感 1｜记仇 2｜已记 2 件事｜NPC：小笼包
```

B1 节点级执行（来自 Dify 数据库 `workflow_node_executions`）：

| 节点 | 状态 | 耗时 | 输出摘要 |
| --- | --- | --- | --- |
| `http_scope` | succeeded | 179 ms | HTTP 201，`scope_id=scp_2m173y9qn52aep9xf4ggky4g1e` |
| `http_ledger` | succeeded | 516 ms | HTTP 200，3 条条目（gift、name、prank） |
| `code_ledger` | succeeded | 101 ms | `intent=recall`，`npc_name=小笼包` |
| `if_write` | succeeded | 114 ms | `false` |
| `if_route` | succeeded | 145 ms | `true` |
| `answer_recall` | succeeded | 28 ms | 回答 + 状态行 |

## 5. 账本快照

运行前：`entries: []`（`scope_existed_before: false`）。

会话 A 后（3 条，按写入时间）：

```
mem_ent_5ca7dd55...  npc-event  type=gift; warmth=2; grudge=0; say=给你带了根猫条，还有热豆浆。
mem_ent_660dbf71...  npc-name   name=小笼包
mem_ent_692afc7f...  npc-event  type=prank; warmth=-1; grudge=2; say=我把货架上的布丁按颜色排成彩虹了，还给价目表画了两撇胡子。
```

会话 B 后：仍为 3 条（B1/B2 不写入）。完整 JSON 见 `../evidence/ledger_dump.json`。

## 6. 界面验证

在同一浏览器打开 WebApp（`/chat/<访问密钥>`）：

1. 发送恶作剧与示好，状态行随轮次变化（`ui-chat-prank.png`）；
2. 点击“新建对话”，发送“你还记得我上次干了什么吗？”，回答仍引用画胡子旧事，
   状态行保持 `好感 1｜记仇 2｜已记 2 件事｜NPC：小笼包`（`ui-recall-new-conversation.png`）；
3. 打开单轮运行详情，看到全部节点与耗时（`ui-workflow-process.png`）。

## 7. 说明

- 运行脚本写入测试用户 `nightshift-demo-04` 的 scope；评审复跑请换新用户。
- 终端若出现中文乱码，设置 `PYTHONIOENCODING=utf-8`。
- 实测未修改 Dify 的 SSRF 配置；HTTP 节点经默认 `ssrf_proxy` 访问 `host.docker.internal` 成功。

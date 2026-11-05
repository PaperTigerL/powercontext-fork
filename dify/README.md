# 打烊之后 · 便利店夜班 NPC（Dify + PowerContext）

> OceanBase 大赛「Dify」生态赛题交付物。
> 本文所有“实测”均指 2026-11-05 在真实的 Dify 1.9.1 与 PowerContext 1.2.0（SeekDB）上跑通的结果，
> 原始日志、节点级执行记录与界面截图都在 [`evidence/`](evidence/)。

---

## 0. 一句话与实测结论

凌晨三点，便利店「夜灯」只剩你和一台会说话的旧补货机。它把店里发生的事记在一本小本子上——
包括你干过的坏事。**小本子不在 Dify 里，而在 PowerContext 的长期记忆里**：
新开一个对话，它照样记得你昨天把布丁排成彩虹、给价目表画了两撇胡子。

实测结论（对应评分项 3.1）：

| 评审关注点 | 本作品的实测情况 | 证据 |
| --- | --- | --- |
| DSL 能在真实 Dify 跑起来 | Dify **1.9.1** 导入 `app.yml`（15 节点 / 15 边，advanced-chat），发布后 5 轮对话全部 HTTP 200 | [`evidence/scenario_run.json`](evidence/scenario_run.json) |
| 主要功能可体验 | 跨会话记忆、记仇/好感累加、改名、翻旧账、闲聊五条路径均有真实回答 | 同上 + 3 张界面截图 |
| 技术结合有效 | 每轮先 `POST /v1/scopes` 取存档、`POST /v1/memory/entries/list` 读账本，再按意图 `POST /v1/memory/remember`；状态由记忆现算 | 节点级 trace、账本前后快照 |
| 过程可复现 | 版本、模型、网络、导入、发布、验证步骤全部写死；附可重跑的脚本 | 本文第 4~6 节 + `scripts/` |
| PowerContext 后端 | `powercontext[cli,server,seekdb]==1.2.0`，`DATABASE_KIND=seekdb`，容器内 `/data/seekdb` 已落盘 | `evidence/README.md` 的部署核验 |

---

## 1. 作品与玩法

玩家是夜班店员，NPC 是旧补货机「团子」（可以改名）。玩家每说一句话，团子先**读完整本小本子**，
按规则判定这句话属于哪类，再把值得记的事写回小本子，最后按账本内容说话。

| 玩家动作 | 判定 | 状态变化 | 写进小本子 |
| --- | --- | --- | --- |
| 恶作剧（彩虹布丁、画胡子、藏东西…） | `prank` | 好感 -1，记仇 +2 | `kind=npc-event` |
| 示好（猫条、热豆浆、擦玻璃…） | `gift` | 好感 +2 | `kind=npc-event` |
| 改名（“以后你就叫小笼包吧”） | `rename` | 改 NPC 名字 | `kind=npc-name` |
| 翻旧账（“你还记得我上次干了什么吗”） | `recall` | 不变 | 不写 |
| 其他 | `smalltalk` | 不变 | 不写 |

意图判定是**纯规则**的（Code 节点），因此状态栏可逐字验收；台词由 LLM 自由发挥。
每条回复末尾固定输出一行：

```
【小本子】好感 1｜记仇 2｜已记 2 件事｜NPC：小笼包
```

这一行不是变量里存的，而是**从 PowerContext 账本现算**出来的。

---

## 2. 实测环境与版本（评分项 4.2）

### 2.1 软件版本

| 组件 | 版本 / 镜像 | 说明 |
| --- | --- | --- |
| 宿主机 | Windows 11（10.0.26300），Docker Desktop（WSL2 后端） | 单机验证 |
| Dify API / Worker / Web | `langgenius/dify-api:1.9.1`、`langgenius/dify-web:1.9.1` | 官方 `docker/docker-compose.yaml` 自托管 |
| Dify 依赖 | PostgreSQL 15、Redis 6、sandbox 0.2.12、nginx、weaviate 1.19.0、ssrf_proxy（ubuntu/squid）、plugin_daemon 0.3.0-local | 共 11 个容器 |
| Dify 访问地址 | `http://127.0.0.1:8088`（`EXPOSE_NGINX_PORT=8088`） | nginx 入口 |
| Dify 模型插件 | `langgenius/openai_api_compatible:0.0.73` | 本地 `.difypkg` 离线安装 |
| 模型服务 | Qwen2.5-3B-Instruct GGUF Q4_K_M + `llama-cpp-python[server]` | `http://127.0.0.1:11435/v1`，别名 `qwen2.5-3b-instruct`，ctx 4096，chatml |
| PowerContext | `powercontext[cli,server,seekdb]==1.2.0` | 容器 `pc-server`，`http://127.0.0.1:8000` |
| PowerContext 后端 | `POWERCONTEXT_SERVER_DATABASE_KIND=seekdb`，数据目录 `/data/seekdb` | 非 SQLite；见 4.1 的落盘核验 |
| PowerContext 鉴权 | `ACCESS_MODE=enforced` + Bearer token | 每个请求都带 `Authorization` |

Dify 侧模型配置（`设置 → 模型供应商 → OpenAI-API-compatible`）：

| 字段 | 值 |
| --- | --- |
| Model Name | `qwen2.5-3b-instruct` |
| Base URL | `http://host.docker.internal:11435/v1` |
| API Key | 本地 llama.cpp 不校验，填任意非空字符串 |
| Model type / mode | LLM / chat |
| Context size | 4096 |
| Max tokens | 2048 |
| API type | chat_completions |
| Compatibility | strict |

> **换模型**：DSL 的两个 LLM 节点当前指向上述模型。评审若使用其他 OpenAI 兼容模型，
> 在 Dify 里配好供应商后，把两个 LLM 节点的模型改成它即可。换模型只影响台词风格，
> **不影响记忆读写与状态栏**（状态栏由 Code 节点计算）。

### 2.2 网络条件

- Dify 容器通过 `host.docker.internal` 访问宿主机上的 PowerContext（8000）与模型服务（11435）。
- Dify 1.9.1 的 HTTP Request 节点默认经 `ssrf_proxy`（squid）出网；官方 squid 配置允许
  Docker 内网来源访问私网地址，本次实测代理与直连均返回 200，**未修改任何 SSRF 配置**。
- 若部署在 Linux，`host.docker.internal` 需要 compose 里的 `extra_hosts: ["host.docker.internal:host-gateway"]`
  （官方 compose 已给 api/worker 配置）；也可改用同一 compose 网络的服务名，或宿主局域网 IP。

### 2.3 无真实密钥入库

- `deploy/.env` 只存在于本机，已加入 `.gitignore`；仓库内只有 `deploy/.env.example`。
- DSL 的 `PC_AUTH_TOKEN` 默认值为空串，导入后由使用者在 Dify 界面填写。
- 两个 LLM 节点不含任何 API Key；密钥属于 Dify 的模型供应商配置，不随 DSL 分发。
- 本文与证据文件中的所有 token、API key 均未记录。

---

## 3. 架构与节点职责

### 3.1 数据流

```text
玩家输入 sys.query / sys.user_id
        │
        ▼
[code_prepare 准备玩家存档]  user_id → scope 标题/幂等键；json.dumps 生成创建体
        ▼
[http_scope 取出玩家存档]    POST /v1/scopes            → 201 + scope_id（幂等）
        ▼
[code_scope 解析存档]        json.dumps({"scope_id": ...}) 生成读账本请求体
        ▼
[http_ledger 翻出小本子]      POST /v1/memory/entries/list → 200 + entries[]
        ▼
[code_ledger 解析账本·判定意图] 重建好感/记仇/名字；判定 prank/gift/rename/recall/smalltalk；
        │                       生成 remember 请求体（仅在需要时）
        ├─[if_write 这轮要记账吗]─true→ [http_remember 记进小本子] POST /v1/memory/remember
        ▼
[if_route 翻账本还是闲聊] ─true→ [llm_recall 团子翻账本] → [code_reply_recall] → [answer_recall]
        └────────────────false→ [llm_chat 团子日常]     → [code_reply_chat]   → [answer_chat]
```

### 3.2 节点清单（15 节点 / 15 边）

| 节点 id | 类型 | 职责 |
| --- | --- | --- |
| `start` | start | 入口，玩家一句话走 `sys.query` |
| `code_prepare` | code | 用 `sys.user_id` 生成 scope 标题/幂等键；`json.dumps` 生成创建请求体 |
| `http_scope` | http-request | `POST /v1/scopes`，幂等取回或创建该玩家的存档 |
| `code_scope` | code | 解析 `scope_id`；`json.dumps` 生成读账本请求体；输出 user/conversation 映射说明 |
| `http_ledger` | http-request | `POST /v1/memory/entries/list` 读回整本小本子 |
| `code_ledger` | code | 从账本重建状态；规则判定意图；生成写回请求体 |
| `if_write` | if-else | 本轮是否产生值得记住的事 |
| `http_remember` | http-request | `POST /v1/memory/remember` 追加一条记忆 |
| `if_route` | if-else | 翻旧账（`recall`）还是日常 |
| `llm_recall` | llm | 翻账本台词：必须引用账本里的具体旧事 |
| `llm_chat` | llm | 日常台词：按好感/记仇语气演出 |
| `code_reply_recall` | code | 清理 LLM 输出并附加 3 条行动选项 |
| `code_reply_chat` | code | 同上（日常分支） |
| `answer_recall` | answer | 台词 + 行动选项 + 状态行 |
| `answer_chat` | answer | 同上 |

> 上一版评审看到的是 10 节点；本版本新增了 `code_prepare`、`http_scope`、`code_scope`
> 与两个 `code_reply_*`，用于**按用户自动建存档**与**稳定输出格式**，不再需要手工填 `PC_SCOPE_ID`。

### 3.3 对象映射（评分项 4.4）

| Dify 对象 | PowerContext 对象 | 映射规则 |
| --- | --- | --- |
| 终端用户 `sys.user_id` | Scope | 标题 `夜灯便利店·夜班存档·<user_id>`；幂等键 `dify-nightstore-<user_id>` |
| 一个 Dify 应用 | Scope 的集合 | 每个终端用户一个存档；同一用户跨会话共用 |
| 会话 `sys.conversation_id` | 不参与 scope 键 | 只写入 `reason` 与 `mapping_note` 便于追溯；**跨会话记忆正是本作品的目的** |
| 角色 NPC | `npc-name` 记忆条目 | 初始「团子」；玩家改名后写 `name=<新名字>`，后续从账本读回 |
| 一轮互动 | `npc-event` 记忆条目 | `type=prank/gift; warmth=±n; grudge=±n; say=<玩家原话>` |

**初始数据**：无。空账本即初始状态：NPC 叫「团子」，好感 0、记仇 0、已记 0 件事。
**重置存档**：换一个 `sys.user_id`（Web 端清空站点数据或开隐身窗口；API 端换 `user` 字段）即可得到全新 scope。

### 3.4 Web 端如何保持同一个存档

Dify Web 应用为每个浏览器生成并持久化一个终端用户 id，**新建对话不会改变它**。
因此“新建对话 → 它还记得”验证的是跨会话记忆，而不是同会话上下文。
如果开隐身窗口或清空站点数据，会得到新 user_id 和新 scope——这是预期的“新存档”。

---

## 4. 部署与运行

以下步骤与本次实测一致。PowerContext 与 Dify 都在本机 Docker 中，端口 8000 / 8088。

### 4.1 启动 PowerContext（SeekDB 后端）

`deploy/docker-compose.powercontext.yaml` 使用 `python:3.11-slim-bookworm` 安装
`powercontext[cli,server,seekdb]==1.2.0`，并以 SeekDB 作为后端：

```yaml
environment:
  POWERCONTEXT_HOME: /data
  POWERCONTEXT_SERVER_HTTP_HOST: 0.0.0.0
  POWERCONTEXT_SERVER_HTTP_PORT: "8000"
  POWERCONTEXT_SERVER_DATABASE_KIND: seekdb
  POWERCONTEXT_SERVER_DATABASE_PATH: /data/seekdb
  POWERCONTEXT_SERVER_ACCESS_MODE: enforced
  POWERCONTEXT_SERVER_AUTH_TOKEN: ${PC_AUTH_TOKEN:?set PC_AUTH_TOKEN}
```

步骤：

```bash
cd dify/deploy
cp .env.example .env
# 编辑 .env，把 PC_AUTH_TOKEN 换成一个随机串，例如：
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose -f docker-compose.powercontext.yaml --env-file .env up -d
curl http://127.0.0.1:8000/health/ready
```

实测返回（2026-11-05）：

```json
{"status":"ready","checks":{"runtime":"ready","database":"ready",
 "access_mode":"enforced","authentication_provider":"ready",
 "access_provider":"ready","access_resource_kinds":"server,scope,artifact"}}
```

后端核验（容器内）：

```bash
docker exec pc-server sh -c 'echo $POWERCONTEXT_SERVER_DATABASE_KIND; powercontext --version; ls -la /data/seekdb'
# seekdb
# 1.2.0
# /data/seekdb/{etc,log,run,store}
```

说明：

- 首次启动要 `pip install`，健康检查 `start_period` 设为 300 秒；本次约 3 分钟就绪。
- `powercontext-data` 是命名卷，删除容器不会丢账本。
- 若使用官方镜像或原生安装，只需保证版本 1.2.0、后端为 SeekDB、并设置同一个 Bearer token。

### 4.2 启动 Dify 1.9.1

使用 Dify 官方 `docker/docker-compose.yaml`（1.9.1），在 `.env` 中设置：

```dotenv
EXPOSE_NGINX_PORT=8088
```

```bash
docker compose up -d
# 首次打开 http://127.0.0.1:8088 完成管理员初始化
```

**离线安装模型插件**：`设置 → 插件 → 安装插件 → 从本地安装`，
选择 `openai_api_compatible.difypkg`（版本 0.0.73）。

### 4.3 启动本地模型（可换成任意 OpenAI 兼容模型）

```bash
pip install "llama-cpp-python[server]"
python -m llama_cpp.server \
  --model /path/to/qwen2.5-3b-instruct-q4_k_m.gguf \
  --model_alias qwen2.5-3b-instruct \
  --host 0.0.0.0 --port 11435 \
  --n_ctx 4096 --n_threads 8 --chat_format chatml
```

然后在 Dify 里按 2.1 的表添加模型。若使用通义千问、DeepSeek、OpenAI 等云模型，
在对应供应商里配好 Key，并把两个 LLM 节点改成该模型即可。

### 4.4 导入 DSL 并发布

1. Dify →「工作室」→「导入 DSL 文件」，选择本目录的 `app.yml`。
2. 打开应用 → 右上角「环境变量」，填入：

   | 变量 | 填什么 |
   | --- | --- |
   | `PC_BASE_URL` | Dify 容器能访问到的 PowerContext 地址（见下表） |
   | `PC_AUTH_TOKEN` | 4.1 中 `.env` 里的同一个 Bearer token |

   | Dify 部署形态 | PowerContext 位置 | `PC_BASE_URL` |
   | --- | --- | --- |
   | Docker Compose | 同一 compose 网络 | `http://powercontext:8000` |
   | Docker Compose | 宿主机 | `http://host.docker.internal:8000`（DSL 默认值） |
   | 原生运行 | 宿主机 | `http://127.0.0.1:8000` |

3. 检查两个 LLM 节点的模型是否为 4.3 配置的模型。
4. **发布**（右上角「发布」→「发布更新」）。修改环境变量后也要重新发布才生效。
5. 进入「访问 API」或「概览 → WebApp 地址」打开 `/chat/<访问密钥>` 开始对话。
   同一浏览器里新建对话不会换存档。

> **不要**手工创建 scope，也不需要 `PC_SCOPE_ID`：第一轮由 `http_scope` 按 `sys.user_id`
> 幂等创建，之后每轮复用。

### 4.5 用脚本复跑验证场景（可选）

```bash
export DIFY_BASE_URL=http://127.0.0.1:8088
export DIFY_APP_API_KEY=app-xxxxxxxx          # Dify 应用「访问 API」里的 key
export POWERCONTEXT_URL=http://127.0.0.1:8000
export POWERCONTEXT_CLIENT_API_TOKEN=<token>  # 与 deploy/.env 一致
export DIFY_DB_CONTAINER=dify-deploy-db-1     # 可选：用于抓节点级执行记录

python scripts/run_scenario.py --user nightshift-demo-04 --out evidence/scenario_run.json
```

脚本会跑「会话 A 三轮（恶作剧/示好/改名）→ 新会话 B 两轮（翻旧账/闲聊）」，
记录每轮的回答、耗时、`workflow_run_id`、节点执行状态与 PowerContext 账本前后快照。
不设置 `DIFY_DB_CONTAINER` 时只抓 API 层记录。

---

## 5. 一次完整的实测样例（评分项 4.3）

**初始状态**：全新用户 `nightshift-demo-04`，此前没有 scope（`scope_existed_before: false`），
账本为空；NPC 名字「团子」，好感 0、记仇 0、已记 0 件事。
**环境**：2.1 所述版本；Dify Web / App API，同一 `user` 字段跨两个会话。
**完整原始记录**：[`evidence/scenario_run.json`](evidence/scenario_run.json)
（含每轮 `workflow_run_id` 与节点级输入/输出/耗时）。

### 5.1 会话 A（同一个 conversation）

| # | 用户输入（原文） | 判定 | 写入 PowerContext | 实际状态行 | 耗时 | workflow_run_id |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 我把货架上的布丁按颜色排成彩虹了，还给价目表画了两撇胡子。 | `prank` | `npc-event`: `type=prank; warmth=-1; grudge=2; say=…` | `【小本子】好感 -1｜记仇 2｜已记 1 件事｜NPC：团子` | 20.8 s | `32ab4822-fec3-4438-94bb-1e55ce759a7d` |
| A2 | 给你带了根猫条，还有热豆浆。 | `gift` | `npc-event`: `type=gift; warmth=2; grudge=0; say=…` | `【小本子】好感 1｜记仇 2｜已记 2 件事｜NPC：团子` | 9.9 s | `f193d014-0aa0-4caa-bfe2-dcce18b22cef` |
| A3 | 以后你就叫小笼包吧。 | `rename` | `npc-name`: `name=小笼包` | `【小本子】好感 1｜记仇 2｜已记 2 件事｜NPC：小笼包` | 12.4 s | `63c2490d-0e88-47d9-8c0e-96ba632cbb19` |

实际回答（节选，完整原文在 evidence）：

- A1：「嚯，这创意不错嘛！不过我得提醒你，下次还是别让店长看到你的杰作。」
- A2：「哎呀，这猫条我可是喜欢的，不过你这豆浆是刚做的吗？有点凉了。」
- A3：「嗯，小笼包？这名字听起来挺暖和的。不过下次别再跟我玩这种小把戏了。」

### 5.2 会话 B（**新建对话**，同一 user）

| # | 用户输入（原文） | 判定 | 实际状态行 | 耗时 | workflow_run_id |
| --- | --- | --- | --- | --- | --- |
| B1 | 你还记得我上次干了什么吗？ | `recall` | `【小本子】好感 1｜记仇 2｜已记 2 件事｜NPC：小笼包` | 19.3 s | `84baf69c-4342-44ba-93a2-026a32ccf037` |
| B2 | 我今天有点困，站了一天。 | `smalltalk` | `【小本子】好感 1｜记仇 2｜已记 2 件事｜NPC：小笼包` | 9.7 s | `fefa312f-0f17-4f42-aa8f-662ff96c11b9` |

B1 的实际回答：

> 记得，你把价目表画了两撇胡子，还站在旁边假装不是你干的。我当时没吭声，小本子上可都记着呢。

这句话里的「价目表画了两撇胡子」只存在于 A1 写进 PowerContext 的 `npc-event` 条目中，
**在 B 会话的上下文里从未出现过**。B1 的节点级记录显示：

| 节点 | 状态 | 耗时 | 关键输出 |
| --- | --- | --- | --- |
| `http_scope` | succeeded | 179 ms | HTTP 201，`scope_id=scp_2m173y9qn52aep9xf4ggky4g1e` |
| `http_ledger` | succeeded | 516 ms | HTTP 200，`entry_count=3`，含 A1/A2/A3 三条条目 |
| `code_ledger` | succeeded | 101 ms | `intent=recall`，`npc_name=小笼包`，状态行 `好感 1｜记仇 2｜已记 2 件事` |
| `if_write` | succeeded | 114 ms | `false`（翻旧账不写入） |
| `if_route` | succeeded | 145 ms | `true`（走翻账本分支） |
| `answer_recall` | succeeded | 28 ms | 上下文回答 + 状态行 |

### 5.3 账本前后快照

- 会话 A 之前：`entries: []`（新建 scope）。
- 会话 A 之后：3 条活跃条目——1 条 `npc-event(gift)`、1 条 `npc-name(name=小笼包)`、
  1 条 `npc-event(prank)`（顺序以接口返回为准）。
- 会话 B 之后：仍为 3 条（B1/B2 均不写入）。
- 完整条目 JSON：[`evidence/ledger_dump.json`](evidence/ledger_dump.json)。

### 5.4 界面截图

| 截图 | 内容 |
| --- | --- |
| [`evidence/ui-chat-prank.png`](evidence/ui-chat-prank.png) | Dify WebApp 中的恶作剧对话与状态行 |
| [`evidence/ui-recall-new-conversation.png`](evidence/ui-recall-new-conversation.png) | **新建对话**后问“你还记得我上次干了什么吗”，仍答出画胡子旧事 |
| [`evidence/ui-workflow-process.png`](evidence/ui-workflow-process.png) | 单轮运行的节点执行面板（节点名、状态、耗时，含 HTTP 节点） |

截图是 2026-11-05 在本机 `http://127.0.0.1:8088/chat/...` 上实际操作的界面。

---

## 6. 证据与复现

### 6.1 证据文件

| 文件 | 说明 |
| --- | --- |
| [`evidence/scenario_run.json`](evidence/scenario_run.json) | 5 轮对话的请求/回答、耗时、`workflow_run_id`、节点级执行记录、账本前后快照 |
| [`evidence/ledger_dump.json`](evidence/ledger_dump.json) | 实测 scope 的完整账本（3 条条目） |
| [`evidence/ui-chat-prank.png`](evidence/ui-chat-prank.png) | WebApp 恶作剧回合 |
| [`evidence/ui-recall-new-conversation.png`](evidence/ui-recall-new-conversation.png) | 新会话翻旧账 |
| [`evidence/ui-workflow-process.png`](evidence/ui-workflow-process.png) | 单轮节点执行面板 |
| [`evidence/README.md`](evidence/README.md) | 每份证据怎么产生、怎么核对，以及后端/版本核验命令 |

节点级记录来自 Dify 自有数据库表 `workflow_runs` / `workflow_node_executions`
（`docker exec dify-deploy-db-1 psql ...`），不是自写模拟器。

### 6.2 复现路径

1. 按第 4 节启动 PowerContext（SeekDB）与 Dify 1.9.1，配好模型。
2. 导入 `app.yml`，填 `PC_BASE_URL` / `PC_AUTH_TOKEN`，发布。
3. 打开 WebApp，在同一个浏览器里依次发送 5.1 的三句话，再**新建对话**发送 5.2 的两句话。
4. 对照每轮状态行；用 `python scripts/inspect_memory.py --user <user_id>` 查看账本。
5. 若需机器记录，运行 4.5 的 `scripts/run_scenario.py`。

> 同一 `user` 的第二次运行会复用已有 scope，账本里会多出条目，状态行不再从零开始。
> 复跑请换一个新 `--user`，或让 WebApp 换一个隐身窗口。

### 6.3 可移植性

- DSL 不包含本机路径、账号、密钥；只有两个环境变量（地址与 token）。
- 模型与 PowerContext 都是标准 HTTP 服务；换宿主机只需改 `PC_BASE_URL` 与模型供应商的 Base URL。
- 节点内代码只用 Python 标准库（`json`/`re`），Dify 沙箱可直接运行。

---

## 7. 对应上次评审意见的修正

| 上次意见 | 本次修正 | 可核对处 |
| --- | --- | --- |
| README 明确写“DSL 未在真实 Dify 导入” | 已在 Dify **1.9.1** 导入、发布并跑完 5 轮；README 不再有“未实测”表述 | 第 0、5 节，`scenario_run.json` |
| 模型仍是 `gpt-4o-mini` 占位 | 实测模型为本地 **Qwen2.5-3B-Instruct**（OpenAI 兼容），版本/参数/启动命令写死；换模型方法明确 | 2.1、4.3 |
| `PC_SCOPE_ID` 为空 | **移除**该变量；改为按 `sys.user_id` 幂等创建/取回 scope（`http_scope`），无需手工填 | 3.3、4.4 |
| 无 `workflow_run_id`、`node_finished/SSE`、transcript 或截图 | 证据包含 5 个 `workflow_run_id`、每轮节点级状态/耗时/输出、完整回答原文、3 张真实界面截图 | 5.1~5.4、`evidence/` |
| `validate_dsl.py` 是自写校验器 + 本地 exec 模拟 | **删除** `validate_dsl.py`；改为真实 Dify 运行记录 + 可复跑的 API 脚本 | 交付物清单 |
| 固定共享 scope、无认证 | 每个 `user_id` 独立 scope；PowerContext `ACCESS_MODE=enforced`，所有 HTTP 节点带 Bearer token | 2.1、4.1 |
| `scope_id` 原样插值 JSON | 所有请求体由 Code 节点 `json.dumps` 生成（含 `scope_id` 与玩家原话） | 3.2、`app.yml` |
| PowerContext 是 SQLite 非 SeekDB | 部署改为 `powercontext[cli,server,seekdb]==1.2.0`，`DATABASE_KIND=seekdb`，`/data/seekdb` 落盘 | 4.1、`evidence/README.md` |
| FTS 词法检索非语义 | 本作品**不依赖 FTS**：只做显式 `remember` 与全量 `entries/list`，状态由全部事件条目精确重建；没有“语义检索”的功能宣称 | 3.1、3.2 |
| 编排是“薄壳/自写重放”的疑虑 | 编排为 15 节点真实 Dify 工作流：HTTP 节点负责存取，Code 节点负责解析/判定/请求体，LLM 节点负责台词，if-else 负责路由 | 3.1、3.2、节点 trace |

---

## 8. 已知边界

1. **3B 模型台词有限**。回答的措辞会波动，有时不如大模型自然；状态栏、写入内容、分支选择
   都是确定性的，可逐字校验。换更大模型只改台词质量。
2. **检索方式是有意选择的全量读取**。NPC 只关心“自己这本账”，条目数量小；用
   `entries/list` 全量读回再精确求和，比 FTS/向量检索更可控，也避免“检索不到就失忆”。
   若账本很长（数千条），应改为分页/摘要，这不在本次验证范围。
3. **scope 隔离依赖 Dify 终端用户 id**。同一浏览器/同一 `user` 共享存档；清空站点数据即新存档。
   PowerContext 的 token 是服务级凭据，不是每用户凭据。
4. **并发写入**。同一用户同时发两轮时，两轮都可能读到旧账本并各写一条；PowerContext 对
   完全相同的条目会去重，但不同措辞会各记一笔。单人夜班场景未处理并发。
5. **平台**。只在 Windows 11 + Docker Desktop 实测；Linux 需确认 `host.docker.internal`
   的解析（见 2.2），或改用服务名/局域网 IP。
6. **模型上下文 4096**。账本摘要只取最近 50 条事件，避免超出上下文。

---

## 9. 常见问题

**Q：第一轮报 401/403。**
A：`PC_AUTH_TOKEN` 与服务端 `.env` 不一致，或 `PC_BASE_URL` 填了 Dify 容器访问不到的地址。
先在 Dify 容器里 `curl -H "Authorization: Bearer <token>" http://host.docker.internal:8000/health/ready` 验证。

**Q：第一轮报 `scope_id` 校验失败 / entries/list 422。**
A：检查 `http_scope` 节点输出状态码是否为 201、body 里是否有 `scope_id`；
若 `http_scope` 失败，后续 `code_scope` 会生成空 `scope_id`。常见原因是地址或 token 错误。

**Q：状态行一直是 0、名字一直是团子。**
A：说明账本没有写入成功。查看 `http_remember` 的响应与 PowerContext 日志；
或运行 `scripts/inspect_memory.py --user <user_id>` 看该用户 scope 是否为空。

**Q：新建对话后失忆。**
A：确认是同一浏览器（同一终端用户），且没有清空站点数据；确认没有换 Dify 应用或改过 `user`。

**Q：导入时提示 DSL 版本较旧。**
A：`version: 0.1.5` 是 Dify 1.x 的 DSL 版本；1.9.1 导入会提示兼容性警告，节点按 1.x 语义加载，
本次实测即在此警告下正常发布运行。

**Q：想清理验证数据。**
A：换新用户即可得到新 scope；旧 scope 留在 PowerContext 中，可用管理接口删除，
或直接删除 `powercontext-data` 卷（会清空全部存档）。

---

## 10. 交付物清单

```text
dify/
├── README.md                     本文件
├── 技术说明.md                    架构、数据流、记忆 schema、接口契约
├── app.yml                       Dify DSL（15 节点 / 15 边，可直接导入）
├── deploy/
│   ├── docker-compose.powercontext.yaml   PowerContext 1.2.0 + SeekDB
│   ├── .env.example              token 占位（真实 .env 不入库）
│   └── dify-1.9.1.env.example     Dify 1.9.1 关键环境变量
├── evidence/
│   ├── README.md                 证据索引与核验方法
│   ├── scenario_run.json         5 轮实测记录（含节点 trace）
│   ├── ledger_dump.json          实测账本快照
│   └── ui-*.png                  3 张真实界面截图
├── samples/
│   ├── session.md                逐轮输入/判定/期望/实际
│   ├── expected-state.json       机器可读期望状态
│   └── verification-log.md       本次实测日志（版本、命令、返回）
└── scripts/
    ├── inspect_memory.py         按 user_id 查 scope 与账本（只读）
    ├── verify_memory_api.py      独立探针 scope 的 remember → list 闭环
    └── run_scenario.py           通过 Dify API 复跑 5 轮并抓证据
```

**作品定位**：Dify 负责编排（15 节点、HTTP/Code/LLM/分支/回答），PowerContext 负责长期记忆
（每用户一个 Scope，显式写入、全量读回、状态现算）。二者职责边界清晰，记忆内容可直接在
PowerContext 中审计，不依赖对话上下文或向量检索。



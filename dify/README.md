# 打烊之后 · 便利店夜班 NPC（Dify + PowerContext）

> OceanBase 大赛「Dify」生态赛题交付物：Dify DSL + 运行说明 + 验证样例。

---

## 1. 作品是什么

凌晨三点，便利店「夜灯」只剩你和一台会说话的老补货机。它叫**团子**（你可以给它改名），
把店里发生的每件事都记在自己的一本**小本子**上——包括你干过的坏事。

你不是来买水的，你是来上夜班的。团子嘴上从不说自己记仇，但小本子记得清清楚楚：
你把布丁按颜色排成彩虹，它记一笔；你给它带猫条，它也记一笔。
下次你再开一个新对话，它照样记得。

**一句话**：一个会跨会话记仇的便利店 NPC。它的一切"记性"都不在 Dify 里，
而在 **PowerContext** 的长期记忆里。

### 玩法

每轮你只做一件事，团子会把它归到四类里，并写进小本子：

| 你的动作 | 判定 | 团子状态变化 | 写进小本子的内容 |
| --- | --- | --- | --- |
| 恶作剧（把布丁排成彩虹、给价目表画胡子…） | `prank` | 好感 -1，记仇 +2 | `kind=npc-event` |
| 示好（带猫条、热豆浆、帮它擦玻璃…） | `gift` | 好感 +2 | `kind=npc-event` |
| 改名（"以后你就叫小笼包吧"） | `rename` | 名字换成新名字 | `kind=npc-name` |
| 翻账本（"你还记得我上次干了什么吗"） | `recall` | 不变 | 不写（只是翻账） |
| 其他闲聊 | `smalltalk` | 不变 | 不写 |

意图判定是**纯规则**的（见 Code 节点），行为可预期，方便验收；台词由 LLM 自由发挥。

### 好玩在哪

1. **它真的记得**。不是把上一轮对话塞进上下文，而是把"你干过什么"作为独立的长期记忆条目
   存在 PowerContext 里。新开一个 Dify 会话、换一个 scope 之外的新对话，团子照样能翻出彩虹布丁那件事。
2. **它记仇，而且是温和的那种**。恶作剧会让它的语气阴阳怪气、开始翻旧账；你再送一次猫条，
   好感度回到正数，它就软下来。状态是从长期记忆里**现算**出来的，不是某个变量里存着的。
3. **状态栏暴露了"它在想什么"**。每条回复末尾都有一行 `【小本子】好感 x｜记仇 y｜已记 n 件事｜NPC：名字`，
   评审能一眼看出记忆有没有落库、状态有没有跨轮累积。

---

## 2. 依赖

| 依赖 | 版本 / 方式 | 说明 |
| --- | --- | --- |
| Dify | 1.0.0 或更高（DSL `version: 0.1.5`） | 需要 Chatflow（高级对话）应用类型与代码/HTTP 节点 |
| PowerContext | 1.2.0 | 只需 **基础记忆** 能力（显式保存 + 召回），**不需要**配置任何模型 API |
| PowerContext 部署 | `uv tool install` 或官方 Docker 镜像 | 见下文第 4 节 |
| 模型提供方 | **需评审自行配置** | DSL 默认写的是 `langgenius/openai/openai` + `gpt-4o-mini`；导入后在 LLM 节点里换成任意可用模型即可 |

> **模型 provider 说明**：本作品**不附带也不申请**任何 API key。两个 LLM 节点的 `model` 字段
> 只是一份占位默认值，导入后请在 Dify 界面里把它改成你已配置好的模型（例如通义千问、DeepSeek、
> OpenAI 等）。换模型只影响台词风格，不影响记忆逻辑。
>
> **PowerContext 不需要模型**：本作品只调用 `POST /v1/memory/remember` 与
> `POST /v1/memory/entries/list`，两者都是显式读写，不需要 Generation / Embedding 凭据。

---

## 3. 交付物清单

```
dify/
├── README.md                        本文件：运行与验收说明
├── 技术说明.md                       架构、节点职责、数据流、记忆 schema、扩展方向
├── dsl/
│   └── night-store-npc.yml          Dify DSL（可直接导入）
└── scripts/
    ├── init_scope.py                初始化 PowerContext Scope，打印要填进 Dify 的环境变量
    ├── verify_memory_api.py         PowerContext 记忆闭环自检（不依赖 Dify）
    └── validate_dsl.py              DSL 结构校验器 + Code 节点实跑 + 端到端闭环自测
```

---

## 4. 运行步骤

### 4.1 启动 PowerContext Server

```bash
uv tool install --force "powercontext[cli,server]==1.2.0"

mkdir -p powercontext-config && cd powercontext-config
powercontext config init --language zh --output .env
# 向导里选择「基础记忆」即可（本作品不需要 Embedding/Generation API）

powercontext server run --env-file .env
```

默认监听 `http://127.0.0.1:8000`，自带 `/health/live`、`/health/ready` 健康检查。

也可以用官方镜像：

```bash
docker build --file docker/Dockerfile -t powercontext-server:local .
docker run --rm --name powercontext-server \
  --publish 127.0.0.1:8000:8000 \
  --volume powercontext-data:/data \
  powercontext-server:local
```

### 4.2 创建存档（Scope）并拿到 scope_id

本作品把"一份存档"映射到一个 PowerContext **Scope**：同一个 scope 里的 Memory 条目，
就是团子的那本小本子。

```bash
cd dify
python scripts/init_scope.py --base-url http://127.0.0.1:8000
```

脚本会做三件事：探测 `/health/live` → 按标题查找或创建 Scope → 打印下面三行环境变量。

> `scope_id` 由 PowerContext 服务端生成，**不是我们能指定的**，所以必须把脚本打印出来的
> `PC_SCOPE_ID` 回填到 Dify 里。

如果 Server 开启了鉴权，给脚本加上 `--token <token>`（或设环境变量 `POWERCONTEXT_CLIENT_API_TOKEN`）。

### 4.3 交叉验证 PowerContext 记忆闭环（可选但推荐）

在动 Dify 之前，先确认 PowerContext 侧读写正常：

```bash
python scripts/verify_memory_api.py --base-url http://127.0.0.1:8000 --scope-id <scope_id>
```

预期输出 `自检通过：remember -> entries/list -> memory/search 三步闭环正常。`
（自检会往 scope 里写一条测试条目，可以用 `/v1/memory/entries/revise` 或 `retire` 清理。）

### 4.4 导入 Dify DSL

1. 打开 Dify → 「工作室 / Studio」→「导入 DSL」。
2. 选择 `dify/dsl/night-store-npc.yml`。
3. 导入完成后打开应用，进入右上角 **「环境变量」**，填入 `init_scope.py` 打印的三项：

   | 变量名 | 填什么 |
   | --- | --- |
   | `PC_BASE_URL` | Dify **能访问到**的 PowerContext 地址（见下表） |
   | `PC_SCOPE_ID` | `init_scope.py` 打印的 scope_id |
   | `PC_AUTH_TOKEN` | Server 未开鉴权就留空；开了就填 Bearer token |

   **Dify 的网络地址对照**（这一步最容易踩坑）：

   | Dify 部署方式 | PowerContext 位置 | `PC_BASE_URL` 填 |
   | --- | --- | --- |
   | Docker Compose | 与 Dify 在同一个 compose 网络 | `http://powercontext:8000`（服务名） |
   | Docker Compose | 跑在宿主机上 | `http://host.docker.internal:8000` |
   | 原生部署（不在容器里） | 跑在宿主机上 | `http://127.0.0.1:8000` |

   DSL 里 `PC_BASE_URL` 的默认值是 `http://host.docker.internal:8000`，对应上表第二行。

4. 点开两个 **LLM 节点**（"团子翻账本"、"团子日常"），把 `model` 改成你已配置的模型 provider。
5. 在「预览 / 调试」面板里发一句话，开始玩。

> **关于 `app.mode`**：DSL 里写的是 `advanced-chat`——这就是 Dify 中 **Chatflow（高级对话）**
> 应用的 mode 取值。Dify 的 `AppMode` 枚举里没有 `chatflow` 这个值（只有 `chat` / `completion` /
> `advanced-chat` / `agent-chat` / `workflow` / `channel`），写 `chatflow` 会导致导入失败。

---

## 5. PowerContext 在作品中承担什么职责

一句话：**PowerContext 是团子的"脑"，Dify 是它的"神经"**。Dify 只负责编排，记忆全部在 PowerContext。

### 5.1 存了什么

| kind | 正文格式 | 含义 |
| --- | --- | --- |
| `npc-event` | `type=prank; warmth=-1; grudge=2; say=<玩家原话>` | 一次值得记住的互动（恶作剧/示好），带状态增量 |
| `npc-name` | `name=小笼包` | 玩家给 NPC 起的新名字 |

正文里的 `type` / `warmth` / `grudge` / `say` 是轻量键值对，Code 节点用 `;` 和 `=` 解析；
玩家原话里的半角 `;` `=` 会被替换成全角，避免破坏格式。

### 5.2 怎么被复用

**每一次对话都先读账本，再算状态。** 这是本作品与"把聊天记录拼进 prompt"的关键区别：

1. `POST /v1/memory/entries/list` 取回该 scope 下**全部活跃条目**；
2. Code 节点遍历条目，把所有 `npc-event` 的 `warmth` / `grudge` **求和**，
   得到当前好感度与记仇值；把最后一条 `npc-name` 作为 NPC 现在的名字；
3. 状态、账本摘要一起进 LLM 提示词，于是团子的语气和台词由**长期记忆**决定；
4. 本轮产生新事件时，`POST /v1/memory/remember` 追加一条新条目。

所以：**好感度不是某个变量里的数，而是每次从长期记忆里现算出来的总和。**
关掉浏览器重开、换一个会话、换一台机器再连同一个 scope，数字照样对得上。

### 5.3 用的接口

| 接口 | 用途 | 请求体 |
| --- | --- | --- |
| `POST /v1/memory/entries/list` | 读回整本小本子 | `{"scope_id": "..."}` |
| `POST /v1/memory/remember` | 追加一条记忆 | `{"scope_id": "...", "kind": "npc-event", "text": "...", "reason": "..."}` |

两条请求都由 Dify 的 **HTTP Request 节点**发出，请求体由 **Code 节点**用 `json.dumps` 生成——
这样玩家输入里的引号、换行不会破坏 JSON。

接口路径与请求体字段来自 PowerContext 仓库的 `openapi/powercontext.yaml`（`RememberMemoryRequest`、
`ListMemoryEntriesRequest`）与 `docs/zh/docs/develop/http-api.md`，不是臆造的。

---

## 6. 验证样例

### 通用前置条件

- PowerContext Server 已启动，`scripts/init_scope.py` 已执行并拿到 scope_id；
- Dify 已导入 `dsl/night-store-npc.yml`，三个环境变量已填写；
- 两个 LLM 节点已配置好可用的模型；
- **样例 1~4 在同一个 scope 上连续进行**（样例 2、3、4 依赖样例 1 的记忆）；
- 每次都在 Dify 应用的「预览 / 调试」面板里发话。回复末尾的
  `【小本子】好感 x｜记仇 y｜已记 n 件事｜NPC：名字` 是状态判定的锚点。

---

### 样例 1：恶作剧被写进长期记忆

- **初始条件**：全新 scope（`init_scope.py` 刚创建，账本为空），NPC 名字为默认的「团子」，
  好感 0 / 记仇 0 / 已记 0 件事。
- **用户输入原文**：

  ```
  我把货架上的布丁按颜色排成彩虹了，还给价目表画了两撇胡子。
  ```

- **操作步骤**：
  1. 在调试面板输入上面这句话并发送；
  2. 观察回复末尾的状态行；
  3. 执行 `python scripts/verify_memory_api.py --base-url ... --scope-id <scope_id>`，
     或直接查账本：
     ```bash
     curl -s -X POST http://127.0.0.1:8000/v1/memory/entries/list \
       -H 'Content-Type: application/json' \
       -d '{"scope_id":"<scope_id>"}'
     ```
- **预期表现**：
  - 状态行为 `【小本子】好感 -1｜记仇 2｜已记 1 件事｜NPC：团子`；
  - 团子的语气明显带"记仇"（阴阳怪气、扬言记账，但不可怕）；
  - PowerContext 里**新增一条** `kind=npc-event` 的活跃条目，正文形如
    `type=prank; warmth=-1; grudge=2; say=我把货架上的布丁按颜色排成彩虹了，还给价目表画了两撇胡子。`

---

### 样例 2：示好被写进长期记忆，状态跨轮累积

- **初始条件**：已完成样例 1。此时账本 1 条事件，好感 -1 / 记仇 2 / 已记 1 件事。
- **用户输入原文**：

  ```
  给你带了根猫条，还有热豆浆。
  ```

- **操作步骤**：在同一对话里发送上面这句话，再查一次 `entries/list`。
- **预期表现**：
  - 状态行为 `【小本子】好感 1｜记仇 2｜已记 2 件事｜NPC：团子`
    （1 = 上一轮的 -1 加本轮的 +2，**说明状态是从长期记忆累加出来的**）；
  - 团子的语气比上一轮软，但仍然有点记仇；
  - 账本里新增第二条 `npc-event`，正文含 `type=gift; warmth=2; grudge=0`。

---

### 样例 3：改名被记住，并在后续互动中复用（跨轮记忆复用）

- **初始条件**：已完成样例 1。
- **用户输入原文**：

  ```
  以后你就叫小笼包吧。
  ```

- **操作步骤**：
  1. 发送上面这句话；
  2. **新开一个对话**（或直接下一轮）问：
     ```
     你叫什么名字？
     ```
- **预期表现**：
  - 改名那轮的状态行为 `【小本子】好感 -1｜记仇 2｜已记 1 件事｜NPC：小笼包`；
  - PowerContext 里新增一条 `kind=npc-name`，正文为 `name=小笼包`；
  - 下一轮问名字时，团子自称**小笼包**——这个名字来自上一轮落库的长期记忆，
    而不是来自上一轮的对话上下文。

---

### 样例 4：翻账本——长期记忆被真正复用的核心验收

- **初始条件**：已完成样例 1（彩虹布丁那件事还在账本里）。
- **用户输入原文**：

  ```
  你还记得我上次干了什么吗？
  ```

- **操作步骤**：
  1. 发送上面这句话；
  2. 观察团子说了什么。
- **预期表现**：
  - 团子**明确提到"彩虹布丁"或"给价目表画胡子"这件事**（这是样例 1 写进 PowerContext 的原文）；
  - 状态行仍为 `【小本子】好感 -1｜记仇 2｜已记 1 件事｜NPC：团子`
    ——数值与样例 1 完全一致，证明它是**读回长期记忆**算出来的，而不是本轮临时算的；
  - 本轮**不新增**记忆条目（`entries/list` 条目数不变）；
  - 团子的语气带出"你终于想起来了"的得意感。

> **这一组是验收的关键**：它同时证明了 ①记忆落库、②记忆跨轮可读、③记忆内容进入了回答。

---

### 样例 5（附加）：闲聊不污染账本

- **初始条件**：已完成样例 1。
- **用户输入原文**：

  ```
  今天外面下雪了。
  ```

- **预期表现**：状态行 `已记 1 件事`（没有增加），账本条目数不变，团子正常闲聊。

---

## 7. 我做了什么校验 / 哪些部分没有实测

### 已实际执行并通过的校验

```bash
cd dify
python scripts/validate_dsl.py        # 需要 PyYAML
```

`scripts/validate_dsl.py` 会真实加载 YAML 并做以下检查，当前**全部通过**（8 项检查，0 失败）：

1. 顶层结构、`app` 段、`workflow` 段字段齐备，`version` 为 `0.1.5`、`kind` 为 `app`；
2. 10 个节点的 id 唯一，`data.type` 都是合法的 Dify 节点类型；
3. 10 条边的 `source`/`target` 都存在，`sourceType`/`targetType` 与节点类型一致，
   `targetHandle` 为 `target`，两个 if-else 节点的 `true`/`false` 分支句柄都齐备；
4. **各节点类型的实体必填字段符合 Dify 节点 schema**——按 Dify 1.0.0 的
   `api/core/workflow/nodes/*/entities.py` 逐项核对：code 的 `code`/`code_language`/`variables`/`outputs`、
   http-request 的 `method`/`url`/`authorization`/`headers`/`params`/`body`、
   llm 的 `model`(provider/name/mode)/`prompt_template`(role/text)/`context`、
   if-else 的 `cases`(case_id/logical_operator/conditions)、
   answer 的 `answer`、start 的 `variables`；
5. 全文扫描所有 `{{#...#}}` 变量引用：系统变量合法、环境变量已声明、
   指向的 code 节点输出确实在 `outputs` 里声明；
6. 两个 HTTP 节点的 body 在替换环境变量后是**合法 JSON**，url 以 `PC_BASE_URL` 开头、
   headers 含 Bearer token 行；
7. **把 Code 节点的 Python 真正 exec 了一遍**：返回的 9 个键与声明的输出**完全一致**，
   且全部为字符串（Dify 的 code 节点对数字输出有精度校验，全用字符串规避）；
8. **端到端闭环自测**：恶作剧 → 生成写入请求体 → 模拟下一轮读回账本 → 重建状态 →
   翻账本能引用"彩虹布丁"旧事；改名轮写入 `npc-name`；示好轮好感度由 -1 累加到 1；
   闲聊轮不写入记忆。

另外：`scripts/init_scope.py` 与 `scripts/verify_memory_api.py` 均已通过语法检查与 `--help` 冒烟。

### 未经真实环境实测的部分（诚实标注）

| 项目 | 状态 |
| --- | --- |
| DSL 在**真实 Dify 实例**中的导入 | **未实测**。DSL 结构按 Dify 1.0.0 的 schema 编写（对照 `api/services/app_dsl_service.py` 的 `CURRENT_DSL_VERSION = "0.1.5"`、`api/core/workflow/nodes/*/entities.py` 的各节点实体、以及 `api/core/workflow/nodes/http_request/executor.py` 的 body 语义），但没有在真实 Dify 容器里导入过 |
| Dify 界面里的模型 provider 切换 | **未实测**，DSL 里只是占位默认值 |
| `host.docker.internal` 在评审的 Dify 部署形态下是否可达 | **未实测**，README 已给出三种部署形态的地址对照，请按实际环境选择 |
| PowerContext 侧的真实联调 | **未实测**。接口路径、请求体字段、响应结构均按仓库 `openapi/powercontext.yaml` 与 `docs/zh/docs/develop/http-api.md` 逐字核对，但没有对着运行中的 Server 打过包 |
| LLM 台词的具体措辞 | 不确定。提示词约束了"必须引用账本里的具体旧事、不得编造"，但具体措辞由评审配置的模型决定 |

### DSL 格式上几个刻意为之的选择

- **HTTP 节点的 `body.type: json`**：Dify 的 json body 要求 `data` **恰好一项**，
  其 `value` 是**整段 JSON 字符串**（运行时才做变量替换再 `json.loads`）。
  所以写入请求体的 JSON 由 Code 节点用 `json.dumps` 生成，HTTP 节点只做一次整体插值。
- **Code 节点所有输出都是字符串**：Dify 1.0.0 的 `_check_number` 会对数字输出做精度检查，
  用字符串输出最稳，也便于直接拼进 Answer 模板。
- **两个 if-else、两个 LLM 节点、两个 Answer 节点**：翻账本与日常闲聊走两条互斥分支，
  各自有自己的提示词与答案节点，避免"引用不存在的分支变量"。
- **不写 `dependencies`**：让 Dify 在导入时从工作流图里自动推导模型插件依赖，
  避免把某个特定插件版本的哈希钉死。

---

## 8. 常见问题

**Q：HTTP 节点报 `Failed to parse JSON`。**
A：`PC_SCOPE_ID` 没填或填错时，body 会变成 `{"scope_id": ""}`（仍是合法 JSON，不会报这个错）；
这个报错通常是变量替换后 JSON 被破坏。请确认 `PC_SCOPE_ID` 填的是 `init_scope.py` 打印的
scope_id，而不是标题。

**Q：HTTP 节点报 `401 Unauthorized`。**
A：PowerContext 开了鉴权但 `PC_AUTH_TOKEN` 没填。填上 token，或把 Server 的鉴权关掉。

**Q：HTTP 节点报 `502 / Connection error`。**
A：`PC_BASE_URL` 的地址 Dify 容器访问不到。请对照 4.4 节的地址表。

**Q：回复里团子提不起旧事。**
A：多半是账本里没有对应条目。先跑 `scripts/verify_memory_api.py` 确认 PowerContext 侧正常，
再用 `entries/list` 看看条目是否真的写进去了。

**Q：想换个存档重来。**
A：再跑一次 `init_scope.py --title "新的存档名"`，会创建新 scope 并打印新的 scope_id，
填回 `PC_SCOPE_ID` 即可。

---

## 9. 参考

- PowerContext HTTP API：<https://powercontext.oceanbase.io/zh/docs/develop/http-api/>
- PowerContext 接口契约（本文档引用字段的来源）：PowerContext 仓库内的
  `openapi/powercontext.yaml`（`RememberMemoryRequest`、`ListMemoryEntriesRequest`、
  `SearchMemoryRequest`）与 `docs/zh/docs/develop/http-api.md`；
  仓库地址 <https://github.com/oceanbase/powercontext>
- Dify DSL 导入导出实现（本文档核对 schema 的来源）：
  <https://github.com/langgenius/dify/blob/1.0.0/api/services/app_dsl_service.py>

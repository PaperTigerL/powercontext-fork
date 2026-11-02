# MemCoach · 记忆复习教练（OceanBase 2026 大赛 · Qoder 赛题参赛包）

> **一句话简介**：把学到的东西存进 PowerContext 长期记忆，之后按主题检索、用记忆内容出题复习，
> 复习结果再反过来决定下次复习先复习哪一条。

**你要解决的真实痛点**：学习、科研和工作中，笔记散落在各处、复习全靠回忆，
而且「三个月前踩过的坑」「上次的决策理由」根本想不起来，只能重新查、重新问、重新踩一遍。
MemCoach 把这些沉淀物变成**可检索、可复用、会累积**的长期记忆：写进去一次，之后每次复习都从记忆里取材，
并且你复习得怎么样也会被记下来、影响下一轮。

---

## 0. 先看这里：这个包里有什么、你还要做什么

| 交付物 | 路径 | 作用 |
| --- | --- | --- |
| 参赛包总说明 | `qoder/README.md`（本文件） | 选型理由、操作清单、运行说明、提测清单、常见坑 |
| 分阶段提示词 | `qoder/PROMPT.md` | 五个阶段的提示词，逐段粘贴给 Qoder |
| 可运行骨架 | `qoder/app/` | 参赛者已写好、Qoder 在其上继续开发的最小可用应用 |
| 骨架运行说明 | `qoder/app/README.md` | 依赖、启动、配置项、目录结构 |
| 验证样例 | `qoder/VERIFICATION.md` | 8 条自检样例 + curl 速查 + 哪些已实测 |
| 开发记录模板 | `qoder/DEVLOG.template.md` | 复制成 `qoder/DEVLOG.md` 逐阶段填写 |

**重要提醒（关系到能不能过审）**

1. **题面要求「项目的主要开发工作必须在 Qoder 中完成」**。骨架是给你打的底座，不是作品本身。
   真正的工作量在 `PROMPT.md` 的五个阶段里——那是你的主要开发过程，也正是评审要核对的「Qoder 做了什么」。
   骨架存在的意义是把最难复现的部分（PowerContext 接口契约、演示/实时双模式、验证脚本）预先搭好，
   让你的 Qoder 工作能直接落在真实功能上，而不是花时间查 API。
2. **硬阻塞（无法代做）**：发布 Qoder Sites 需要**参赛者本人的 Qoder 个人账号**，
   任何人都无法代劳。本包已经把「开发」部分做到最少操作，但「发布」这一步必须你本人做。
   企业版账号**无法设置「任何人都可访问」**，必须用个人账号。

---

## 1. 项目定位与选型理由（对照题面「技术结合要求」）

题面要求「必须实际使用 seekdb 或 PowerContext 中至少一种，并让其在功能中真正发挥作用」。
本作品选择 **PowerContext**，并且它承担的是**数据底座**而不是装饰性组件：

**PowerContext 在本作品里就是那个"记忆库"本身。** 卡片、复习记录、掌握度全部存成 PowerContext 的 Memory 条目，
应用不维护自己的数据库；关掉浏览器、换一台机器、几天后再回来，记忆都还在，因为它们在 PowerContext 里。
界面上显示的 `entry_id` / `entry_version_id` / `version` / `state` 是 PowerContext 返回的不可变引用，不是本地数组的下标。

### 数据流：写入 → 检索 → 复用 → 用户可见

```
① 用户录入一张学习卡片
      │  POST /api/cards
      ▼
② 后端组装成可检索的正文，写真实存储
      │  POST /v1/memory/remember      { scope_id, kind:"study-card", text, reason }
      │  ← 返回 { memory, entry:{ citation:{entry_id, entry_version_id}, version, kind, text, state } }
      ▼
③ 记忆库面板把整个 scope 的条目读回来
      │  POST /v1/memory/entries/list  { scope_id }
      │  ← { memory, entries:[ MemoryEntry ] }
      ▼
④ 用户输入一个复习主题
      │  POST /v1/memory/search        { scope_id, query, limit, mode:"fts" }
      │  ← { mode, hits:[ { citation, text, score, matched_by } ] }
      ▼
⑤ 用命中条目的正文（points）派生复习题，并把来源标注在题目上
      │  POST /api/review/session
      ▼
⑥ 用户标记「已掌握 / 需加强」，结果再写成一条记忆
      │  POST /v1/memory/remember      { kind:"review-outcome", text:"review=<entry_id> | verdict=weak | note=... | at=..." }
      ▼
⑦ 下次复习时读回 review-outcome，算出掌握度，决定排序
      └─  用户可见效果：题目内容来自你写过的记忆；标注来源 entry_id 与检索得分；
          「需加强」的卡片排在最前；学习足迹里的已掌握/需加强/未复习实时变化。
```

**四处具体的"发挥作用"，不是泛泛而谈：**

| 作用点 | 具体体现 | 没有它会怎样 |
| --- | --- | --- |
| 持久化 | 所有卡片与复习结果作为 Memory 条目存在 PowerContext，换设备/换会话不丢 | 只能存浏览器 localStorage，换台机器记忆就没了，谈不上"长期记忆" |
| 检索 | 按主题从 scope 里检索出相关条目，用它们的正文出题 | 复习题只能靠模板随机生成，和你真正学过的东西无关 |
| 复用 | 复习题直接引用记忆条目的要点，并标注来源 `entry_id` 与 `score` | 用户无法确认题目是不是"我的记忆"，闭环断在这里 |
| 累积 | 复习结果作为新条目写回，掌握度决定下次排序 | 每次复习都从零开始，记忆不"越用越值钱" |

**为什么是 PowerContext 而不是 seekdb**：本作品的核心是**语义化的记忆条目**（不可变引用、精确 citation、
scope 隔离、检索命中打分），这正是 PowerContext Memory API 的设计目标；
seekdb 更适合结构化表与向量检索。如果把卡片做成一张表，条目就没有稳定的不可变引用，
「这次复习题来自哪条记忆」就无法精确标注。PowerContext 还省掉了造表与迁移的工作量，
让 Qoder 的开发时间花在功能上而不是数据建模上。

---

## 2. 参赛者分步操作清单

> 全程大约 1~2 小时（不含你把功能做扎实的时间）。按顺序做，不要跳。

### 步骤 1 · 打开 Qoder，确认仓库状态（5 分钟）

1. 克隆或打开仓库工作副本，切到分支 `2026-competition-ecosystem`。
2. 在 Qoder 里**打开仓库根目录**（不是只打开 `qoder/app`）——这样 Qoder 才能同时读到
   `openapi/powercontext.yaml` 和 `dify/` 里的参考实现，接口字段才不会写错。
3. 先让骨架跑起来，确认环境没问题：

   ```bash
   cd qoder/app
   node server.js
   # 浏览器打开 http://127.0.0.1:8899
   ```

   能看到五个面板就说明 Node 环境正常。

### 步骤 2 · 准备 PowerContext（实时模式才需要；15 分钟）

- 没有集群也能继续：默认就是演示模式，评审照样能完整体验。
- 有集群的话：

  ```bash
  # 在仓库根目录
  python dify/scripts/init_scope.py --base-url http://127.0.0.1:8000
  # 会打印 scope_id；Server 开了鉴权再把 token 一起记下
  python dify/scripts/verify_memory_api.py --base-url http://127.0.0.1:8000 --scope-id <scope_id>
  ```

  这两个脚本是仓库里**已验证可运行**的，输出的 `scope_id` 与 token 就是运行说明里要填的值。
  另有一个免安装选项：启动时加 `POWERCONTEXT_AUTO_SCOPE=1`，本应用会用固定幂等键自动建 Scope。

### 步骤 3 · 按 PROMPT.md 逐阶段推进 Qoder（主要工作量）

1. 打开 `qoder/PROMPT.md`。
2. **阶段 1** 整段复制提示词 → 粘贴给 Qoder → 读它的产出 → 把「本阶段小结」复制进 `qoder/DEVLOG.md`。
3. **阶段 2 → 3 → 4 → 5** 同样重复，一次一个阶段。
4. 每阶段结束都跑一次该阶段「建议的验收命令」，通过再进下一阶段。
5. 第一步先复制模板：

   ```bash
   cp qoder/DEVLOG.template.md qoder/DEVLOG.md   # Windows: copy qoder\DEVLOG.template.md qoder\DEVLOG.md
   ```

> 为什么不能一次性粘完：题面要核对的正是"需求拆解、编码、调试各环节 Qoder 做了什么"。
> 一次性粘完，Qoder 不会产生可核对的中间产出。

### 步骤 4 · 调试（20 分钟）

```bash
cd qoder/app
node scripts/selftest.js          # 端到端自检，期望 15 个断言全 PASS
```

- 实时模式联调：把 `POWERCONTEXT_URL` / `POWERCONTEXT_SCOPE_ID` 配好后重启服务，
  再跑一次 `selftest.js`，看 `/api/health` 的 `mode` 变成 `live`。
- 用 `qoder/VERIFICATION.md` 的 V1~V8 逐条自测，把结果写进 `DEVLOG.md` 的阶段 4。
- 前端改不动时：浏览器 F12 看 Network / Console；接口都有明确的 `error.code`，
  可以直接把报错贴给 Qoder 让它定位。

### 步骤 5 · 用 Qoder Sites 发布并设为公开（20 分钟）

1. 在 Qoder 里打开 `qoder/app/public`（或按 Qoder Sites 的入口选择发布根目录），
   发布**静态站点**。本项目无需构建：`public/` 就是最终产物，且零依赖。
2. 发布后立刻把**可见范围设为「任何人都可访问」**。
   - ⚠️ **企业版账号无法设置公开访问，必须用个人账号。** 这是本赛题最容易卡住的一步。
   - ⚠️ 设成"仅团队/仅自己"会在基础验收第一条直接判定不通过。
3. 发布后用**无痕窗口**（不登录任何账号）打开网址，确认页面完整可用 → 这就是 V1。
4. 把网址填进本文件第 6 节的提测清单。

### 步骤 6 · 整理 Qoder 开发记录（20 分钟）

1. `qoder/DEVLOG.md`：五个阶段的小结、命令与真实输出（`PROMPT.md` 已经强制要求 Qoder 每阶段输出小结）。
2. Qoder 客户端里的会话历史：用客户端自带的**导出/复制会话**功能导出一份，放到仓库 `qoder/` 下
   （例如 `qoder/qoder-session-<阶段名>.md`），或在 `DEVLOG.md` 里写明会话在客户端中的位置。
3. 两者都要有：文字小结说明"做了什么"，会话原文说明"怎么做的"。

### 步骤 7 · 提测前最后核对

见第 6 节提测清单 + 第 7 节常见坑。

---

## 3. 运行说明（可直接抄给评审）

### 3.1 依赖

- **Node.js ≥ 18**（需要原生 `fetch`）。**不需要 `npm install`**——本项目零第三方依赖。
- 演示模式不需要任何其他东西。
- 实时模式需要一台可访问的 PowerContext Server。

### 3.2 启动

```bash
cd qoder/app
node server.js
# 打开 http://127.0.0.1:8899        （端口被占用时：PORT=9000 node server.js）
```

### 3.3 环境变量

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `POWERCONTEXT_URL` | 实时模式必填 | PowerContext Server 基地址，如 `http://127.0.0.1:8000` |
| `POWERCONTEXT_SCOPE_ID` | 实时模式必填 | 记忆所在 scope。别名：`POWERCONTEXT_SCOPE`、`PC_SCOPE_ID` |
| `POWERCONTEXT_TOKEN` | 视情况 | Bearer token。Server 开启鉴权时必填。别名：`POWERCONTEXT_CLIENT_API_TOKEN`、`PC_AUTH_TOKEN` |
| `POWERCONTEXT_AUTO_SCOPE` | 否 | 设 `1` 时自动创建/复用 Scope（幂等键固定） |
| `MEMCOACH_MODE` | 否 | `auto`（默认）/ `demo` / `live` |
| `MEMCOACH_SEARCH_MODE` | 否 | 检索模式，默认 `fts`（最小 Server 的全文检索）；可设 `auto`/`hybrid` |
| `PORT` | 否 | 默认 `8899` |
| `MEMCOACH_TIMEOUT_MS` | 否 | 默认 `15000` |

### 3.4 PowerContext 地址与 token 从哪来

- **地址**：默认 `http://127.0.0.1:8000`（PowerContext Server 的默认监听地址），
  部署在远端就填远端地址。
- **scope_id**：用仓库里的 `dify/scripts/init_scope.py` 创建/复用，它会直接打印 scope_id 与要填的环境变量；
  或用 `POWERCONTEXT_AUTO_SCOPE=1` 让应用自动创建。
- **token**：Server 未开启鉴权时不需要；开启鉴权后由 Server 管理员签发，
  放在 `POWERCONTEXT_TOKEN` 环境变量里（**只放服务端，不要写进前端文件、URL 或日志**）。

### 3.5 PowerContext 不可用时

| 情况 | 表现 |
| --- | --- |
| 没配地址/scope | 自动进入演示模式，`GET /api/health` 的 `mode=demo`，页面照常可用（用内置样例数据） |
| 强制 `live` 但缺配置 | 服务正常启动，相关接口返回 `503 powercontext_not_configured` 并说明怎么配 |
| 配了但连不上 | 接口返回 `502 powercontext_unreachable`（带目标 URL 与原因），进程存活 |
| 静态站点访问、后端填错 | 前端自动回落到内置演示模式，页面顶部有徽章提示 |

### 3.6 自检命令

```bash
cd qoder/app
node scripts/selftest.js
```

---

## 4. 交付物清单（对应题面「提交产物」）

| 题面要求 | 本包中的位置 |
| --- | --- |
| 项目网站网址 | 发布后填入第 6 节；静态产物在 `qoder/app/public/` |
| 代码仓库 | 仓库地址 + 分支 `2026-competition-ecosystem`（见第 6 节） |
| 运行说明 | 本文件第 3 节（可直接整段复制给评审） |
| 验证样例 | `qoder/VERIFICATION.md`（8 条） |
| Qoder 开发记录 | `qoder/DEVLOG.md`（由 `DEVLOG.template.md` 填写）+ Qoder 会话导出 |

---

## 5. 目录结构

```
qoder/
├── README.md              本文件
├── PROMPT.md              五个阶段的提示词
├── VERIFICATION.md        8 条验证样例
├── DEVLOG.template.md     开发记录模板（复制成 DEVLOG.md）
└── app/                   可运行骨架
    ├── README.md          骨架运行说明
    ├── package.json
    ├── server.js
    ├── src/               后端（配置 / 错误 / PowerContext 客户端 / store / 路由 / 静态）
    ├── scripts/           selftest.js（端到端自检）、mock-powercontext.js（契约桩）
    └── public/            前端静态站点（可直接被 Qoder Sites 托管）
```

---

## 6. 提测提交清单

把本表逐项填好后提交。**注意区分"要填的值"和"要核对的值"——填反是常见的失分点。**

| 平台字段 | 填什么 | 怎么拿到 | 核对要点 |
| --- | --- | --- | --- |
| 仓库 URL | `<你的仓库地址>` | 仓库首页复制 | 要能匿名访问；私有仓库评审打不开 |
| 分支 | `2026-competition-ecosystem` | 固定值 | 不是 `main`、不是 `master` |
| Commit SHA | `<40 位 commit SHA>` | `git rev-parse HEAD` | **必须是 40 位完整 SHA**，不是短 SHA、不是分支名；且这个 commit **必须已经 push 到上面那个仓库** |
| 项目网站网址 | `<Qoder Sites 网址>` | 发布后复制 | 未登录能打开（用无痕窗口验证过再填） |
| 可见范围 | 任何人都可访问 | Qoder Sites 设置 | **不是**"仅自己/仅团队"；企业版账号无法设置公开访问，须用个人账号 |
| 技术选型 | PowerContext | — | 题面要求至少用一种（seekdb 或 PowerContext），本作品用 PowerContext |
| 运行说明 | 本文件第 3 节 | — | 评审只按这段跑，别指望口头补充 |
| 验证样例 | `qoder/VERIFICATION.md` | — | 至少 5 条；本包给了 8 条 |
| Qoder 开发记录 | `qoder/DEVLOG.md` + Qoder 会话导出 | 五个阶段的小结 | 要能看出需求拆解 / 编码 / 调试各环节 Qoder 做了什么 |

**提交前最后三条自查：**

```bash
# 1）commit 是否已推送、SHA 是否 40 位
git rev-parse HEAD          # 期望输出 40 位十六进制
git status -sb              # 期望看到分支与远端同步，没有未推送的提交

# 2）网站是否真的公开（用无痕窗口打开上面的网址）
# 3）演示模式是否仍然独立可用（拔掉后端/清空环境变量后跑 node server.js）
```

---

## 7. 常见坑清单

**发布与访问**

1. **企业版账号发不了公开站点**：题面明确说企业版账号无法设置"任何人都可访问"。
   → 发布前确认你用的是**个人账号**。这是最高频的卡点。
2. **可见范围忘了改**：发布成功≠公开。默认可能是"仅自己"。
   → 发布完立刻用**无痕窗口**打开网址验证。
3. **发布根目录选错**：发布的是 `qoder/app/public`，不是 `qoder/app`。
   → 选错的话评审会看到目录列表或 404。
4. **绝对路径导致静态站点白屏**：前端资源必须用 `./xxx.js` 相对路径。
   → 骨架里已经是相对路径，改动时别改成 `/xxx.js`。
5. **前端把 token 写进 public/**：任何人都能看到。
   → token 只能在服务端环境变量里；发布前跑一遍
     `grep -rn "Bearer\|POWERCONTEXT_TOKEN=" qoder/app/public`。

**接口与联调**

6. **CORS**：Qoder Sites 页面与 Node 后端不同源时，浏览器会拦。
   → 骨架后端已经加了 `Access-Control-Allow-Origin: *`；如果你在前端改过，别把这行删了。
   → 更省事的做法：静态站点在页面右上角「后端地址」里填后端地址。
7. **scope 不对**：换了 scope 就看不到之前存的记忆；`scope_id` 写错时 PowerContext 返回 404。
   → 用 `dify/scripts/init_scope.py` 重新拿一份，别手写。
8. **scope 填反**：应用连的是一个 scope，评审用另一个 scope 去查，自然查不到。
   → 运行说明里要写清用的是哪个 scope，以及怎么用 `entries/list` 复核。
9. **检索无命中**：最小 Server 只支持全文检索，语义词搜不到。
   → `MEMCOACH_SEARCH_MODE=fts`（默认）；确认关键词在条目正文里真的出现过。
   → 端点选了 `vector` 但 Server 没配 Embedding，会直接失败。
10. **正文超长**：PowerContext 的 memory 正文上限是 8192 个 UTF-8 字节（NFC 规范化并 trim 之后），
    超了返回 422 `text-too-long`。
    → 骨架已做前置校验并返回同样的错误码，长要点请拆成多条卡片。
11. **鉴权失败 401**：token 没配或配错。
    → 错误信封里会带 `upstream_status` 与 `request_id`，用 `request_id` 去查 Server 日志。

**提交与记录**

12. **commit 没推送就填 SHA**：本地 SHA 填上去，评审拉不到代码。
    → 填之前先 `git status -sb` 确认与远端同步。
13. **SHA 填成短 SHA 或分支名**：平台要求 40 位完整 SHA。
    → `git rev-parse HEAD`。
14. **分支填成 main**：本作品在 `2026-competition-ecosystem` 分支上。
15. **开发记录事后补写**：凭印象补的过程记录通常补不完整，评审一眼能看出。
    → 每个阶段结束就先存小结再进下一阶段。
16. **只有演示模式、没有真实联调证据**：题面明确"不能只是装个组件测连通"。
    → 至少要有一次真实 PowerContext 的写入 + `entries/list` 读回 + `search` 命中的实测输出（截图或日志）。
17. **端口被占用**：本机 8787/8899 可能已被别的服务占用。
    → `PORT=9000 node server.js`，并把该端口写进运行说明。

---

## 8. 诚实标注：哪些已实测、哪些没有

### 已实际执行并通过的

| 项 | 结果 |
| --- | --- |
| `node --check` 覆盖 `qoder/app/` 全部 JS 文件 | 全部通过（14 个文件） |
| 演示模式端到端自检 `node scripts/selftest.js` | 7 个环节 15 个断言全部 PASS，退出码 0 |
| 实时路径对着 **PowerContext 契约桩**（`scripts/mock-powercontext.js`）跑通 | remember → entries/list → search → 出题 → 记掌握度 → 统计，15/15 PASS |
| PowerContext 未配置（`MEMCOACH_MODE=live` 且无配置） | 返回 `503 powercontext_not_configured`，进程存活 |
| PowerContext 地址不可达 | 返回 `502 powercontext_unreachable`（带目标 URL），进程存活 |
| 8192 字节正文上限 | 返回 `422 text-too-long`，错误码与 PowerContext 一致 |
| 静态资源托管与路径穿越防护 | 页面与 5 个静态资源均 200；`../server.js` 被 403 拦截 |

### 未经真实环境实测（需要你完成）

| 项 | 说明 |
| --- | --- |
| **真实 Qoder Sites 发布** | 本包没有真实的 Qoder Sites 网址，也没有任何发布记录；发布步骤是按题面描述与通用流程写的，实际入口名称请以你客户端里看到的为准 |
| **真实 PowerContext Server 联调** | 实时路径是对着**我自己写的契约桩**验证的（路径、字段名、响应结构都对齐 `openapi/powercontext.yaml`），**没有**在真实集群上跑过 |
| **PowerContext 检索命中效果** | 真实 Server 的检索实现（全文/向量/混合）与桩不同，实际召回质量需要你实测 |
| **在 Qoder 客户端里的五阶段推进** | 提示词是按 Qoder 的工作方式写的，但没有在真实 Qoder 会话里逐段试过；请按 `PROMPT.md` 的验收命令逐阶段核对 |
| **跨用户 / 鉴权的部署形态** | 骨架只服务单用户单 scope，没有做登录与多租户隔离 |
| **Qoder Sites 是否支持服务端** | 按纯静态托管设计（前端内置演示模式兜底）；若 Qoder Sites 支持服务端部署，实时模式可以省掉"另部署后端"这一步 |

### 关于「主要开发工作在 Qoder 中完成」

骨架是起点，不是交付物本身。本包的定位是：把接口契约、双模式、验证脚本这些**可复现的基础工作**预先做好，
让你在 Qoder 里的时间花在真正的功能开发上，并且每个阶段都有可核对的产出与验收命令。
**你要交的是五个阶段的 Qoder 开发记录 + 在骨架上做出来的功能。**

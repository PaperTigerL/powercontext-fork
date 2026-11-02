# MemCoach 骨架 · 运行说明

这是 OceanBase 2026 大赛「Qoder」赛题参赛作品《MemCoach · 记忆复习教练》的**可运行骨架**。
参赛者在 Qoder 里继续开发的就是这份代码。

- 零第三方依赖：只用 Node 内置的 `http` 与原生 `fetch`，**不需要 `npm install`**。
- 两种模式：**演示模式**（内置样例数据，无需任何后端）与**实时模式**（真实读写 PowerContext）。

---

## 1. 环境要求

| 项 | 要求 | 说明 |
| --- | --- | --- |
| Node.js | ≥ 18 | 需要原生 `fetch` 与 `AbortSignal.timeout`；已在 Node 22 上验证 |
| npm | 非必需 | 只有一个 `package.json`（无依赖），不需要安装任何包 |
| PowerContext Server | 实时模式才需要 | 见第 4 节 |

## 2. 启动

### 2.1 演示模式（零配置，评审开箱即可体验）

```bash
cd qoder/app
node server.js
# 打开 http://127.0.0.1:8899
```

也可以用 `npm start`（等价）。本机 8899 被占用时用 `PORT=9000 node server.js`。

### 2.2 实时模式（真实读写 PowerContext）

```bash
cd qoder/app

# PowerContext Server 地址与 Bearer token（Server 开启鉴权时才需要 token）
export POWERCONTEXT_URL=http://127.0.0.1:8000
export POWERCONTEXT_SCOPE_ID=<你的 scope_id>
export POWERCONTEXT_TOKEN=<可选的 bearer token>

node server.js
```

`scope_id` 的获取方式（用仓库里已验证的脚本，不要自己发明）：

```bash
# 在仓库根目录（powercontext-ecosystem）执行
python dify/scripts/init_scope.py --base-url http://127.0.0.1:8000
# 或者让本应用用固定幂等键自动创建
POWERCONTEXT_AUTO_SCOPE=1 node server.js
```

### 2.3 端到端自检

```bash
node scripts/selftest.js                      # 默认 http://127.0.0.1:8899
node scripts/selftest.js http://127.0.0.1:9000
```

自检覆盖 7 个环节、15 个断言：健康检查 → 记忆库 → 写入卡片 → 条目进库 → 检索命中 →
复习出题 → 记录掌握度 → 统计与卡片掌握度回显。全部通过时退出码为 0。

## 3. 配置项

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `8899` | 后端监听端口 |
| `MEMCOACH_MODE` | `auto` | `auto`（配了 PowerContext 就实时，否则演示）/ `demo`（强制演示）/ `live`（强制实时，缺配置时接口返回 503 而不是崩溃） |
| `POWERCONTEXT_URL` | 空 | PowerContext Server 基地址，如 `http://127.0.0.1:8000` |
| `POWERCONTEXT_SCOPE_ID` | 空 | 记忆所在 scope。别名：`POWERCONTEXT_SCOPE`、`PC_SCOPE_ID` |
| `POWERCONTEXT_TOKEN` | 空 | Bearer token。别名：`POWERCONTEXT_CLIENT_API_TOKEN`、`PC_AUTH_TOKEN` |
| `POWERCONTEXT_AUTO_SCOPE` | 空 | 设为 `1` 时，若未配置 scope 则用固定幂等键自动创建/复用 Scope |
| `MEMCOACH_SEARCH_MODE` | `fts` | `POST /v1/memory/search` 的 `mode`：`fts`（最小 Server 的全文检索）/ `auto` / `hybrid` / `vector` |
| `MEMCOACH_TIMEOUT_MS` | `15000` | 调用 PowerContext 的超时（毫秒） |

## 4. PowerContext 不可用时怎么办

骨架不会因此崩溃，三种情况都有明确表现：

| 情况 | 表现 |
| --- | --- |
| 没配 `POWERCONTEXT_URL` / `POWERCONTEXT_SCOPE_ID` | `MEMCOACH_MODE=auto` 时自动进入演示模式，`GET /api/health` 的 `mode` 字段是 `demo`，`reason` 写明原因 |
| `MEMCOACH_MODE=live` 但配置缺失 | 服务照常启动；`/api/cards` 等接口返回 `503` + `powercontext_not_configured`，并提示改用 `dify/scripts/init_scope.py` 或 `POWERCONTEXT_AUTO_SCOPE=1` |
| 配了地址但连不上 | 接口返回 `502` + `powercontext_unreachable`，报文里带目标 URL 与原因；进程存活，可继续排查 |

前端侧还有一层兜底：`public/index.html` 作为纯静态页打开（Qoder Sites 直接托管 `public/`）时，
前端检测不到后端就自动切换到内置演示模式，页面上会有「演示模式（内置数据）」徽章。

## 5. 目录结构

```
qoder/app/
├── package.json              零依赖清单；npm start / npm run check
├── server.js                 入口：原生 http 服务、路由分发、JSON 错误信封、静态托管
├── src/
│   ├── config.js             读环境变量，决定 demo/live 模式与各项默认值
│   ├── errors.js             AppError：HTTP 状态码 + 机器可读 error code
│   ├── powerContextClient.js PowerContext HTTP 客户端（remember/search/entries-list/scopes/health）
│   ├── powerContextStore.js  实时模式 store：把 PowerContext 三个 Memory 接口包装成 MemoryStore
│   ├── store.js              按配置选择 store：实时版或演示版
│   ├── routes.js             业务接口：/api/health、/api/cards、/api/search、/api/review/*、/api/stats
│   └── static.js             静态文件服务（含路径穿越防护）
├── scripts/
│   ├── selftest.js           端到端自检脚本（15 个断言）
│   └── mock-powercontext.js  PowerContext 契约桩，仅供离线联调，**不是**真实验证
└── public/                   前端（纯静态，可直接被 Qoder Sites 托管）
    ├── index.html            五个面板：录入 / 记忆库 / 检索 / 复习 / 足迹
    ├── styles.css            样式
    ├── app.js                前端逻辑：后端适配器 + 演示适配器，两种模式同一套渲染
    ├── domain.js             前后端共用的领域逻辑（条目格式、解析、出题、掌握度、排序）
    ├── demo-data.js          演示模式的内置样例数据（5 张卡片 + 1 条复习记录）
    └── demo-store.js         演示模式 store：内存版 Memory，返回结构与实时模式完全一致
```

## 6. 接口一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 模式、PowerContext 地址、scope_id、检索模式、错误原因 |
| GET | `/api/entries` | 记忆库原始条目（对应 `POST /v1/memory/entries/list`） |
| GET | `/api/cards` | 学习卡片列表（附带掌握度） |
| POST | `/api/cards` | 保存一张卡片（对应 `POST /v1/memory/remember`） |
| POST | `/api/search` | 检索记忆（对应 `POST /v1/memory/search`） |
| POST | `/api/review/session` | 按主题检索并生成复习会话 |
| POST | `/api/review/answer` | 记录一次复习结果（写 `review-outcome` 条目） |
| GET | `/api/stats` | 学习足迹统计 |

## 7. 记忆条目的正文格式

PowerContext 的 memory 是自由文本，本项目用一套可解析的小格式（前后端共用 `public/domain.js`）：

```
card=<标题> | type=<concept|decision|pitfall|fact> | points=<要点1> ; <要点2> | tags=<t1,t2> | src=<出处>
review=<被复习的 entry_id> | verdict=<strong|weak> | note=<备注> | at=<ISO 时间>
```

用 ` | ` 分字段、` ; ` 分要点，是为了在最小 Server 的全文检索下也能稳定命中，
同时人能直接读懂。`entry_id` 既是 PowerContext 返回的不可变引用，也用来把复习结果关联回原卡片。

## 8. 已知限制

- **未与真实 PowerContext Server 联调**：本骨架的实时路径是对着 `scripts/mock-powercontext.js`
  这个契约桩验证的（路径、字段名、响应结构），真实 Server 的联调需要参赛者完成。
- `POST /v1/memory/search` 默认用 `mode=fts`。若真实 Server 配了向量检索，可改成 `hybrid`。
- 目前没有鉴权、没有多用户：每个使用者应当使用**自己的 scope_id**（scope 是数据分区键，不是访问控制）。
- 复习题由规则确定性生成，不调用大模型，因此不依赖任何模型 API Key。

# MiniMax 赛题交付包 · 规有所依——面向软件持续演进的 SDD 上下文管理系统

> 本目录是 MiniMax 赛题的作品材料，放在参赛仓库的 `minimax/` 目录下。
> 评测基线分支：`2026-competition-ecosystem`；资产目录：`minimax/`。

---

## 1. 一页技术说明（材料 6）

### 1.1 模块结构

```
minimax/
├── ctxmodule/                    上下文模块本体
│   ├── config.py                 环境变量配置（不含任何硬编码凭据）
│   ├── seekdb_store.py           规格 / 代码 / 测试的存储与检索（嵌入式 seekdb）
│   ├── pc.py                     PowerContext HTTP 客户端 + 任务状态存取
│   ├── llm.py                    MiniMax 调用与录制会话回放
│   ├── pipeline.py               端到端流程（导入 → 选材 → 改码 → 测试 → 存状态）
│   └── cli.py                    统一入口（python -m ctxmodule <command>）
├── sample_project/               被修改的业务工程（可运行的样例）
│   ├── specs/billing_filter_v1.md    规格 v1
│   ├── specs/billing_filter_v2.md    规格 v2（新增 status 过滤）
│   ├── src/billing/filter.py         修改前快照（缺 status 过滤）
│   └── tests/                       目标功能测试 + 回归测试
├── transcript/                   MiniMax 开发记录与产出补丁
│   ├── minimax_session.jsonl        开发记录（请求 / 响应 / 上下文摘要 / diff 摘要）
│   ├── feature.patch                MiniMax 产出的统一 diff
│   └── after/src/billing/filter.py  修改后快照
├── verify/                       六项必做项的验收门禁（pytest）
├── scripts/record_session.py     录制开发会话（--live / --bootstrap）
├── run_selftest.sh               一键自测
├── materials/                    六份材料的填写说明与模板
└── Makefile
```

### 1.2 三项技术的分工

| 技术 | 承担的作用 | 在代码中的落点 |
| --- | --- | --- |
| **MiniMax** | 参与本次任务的代码生成 / 修改 | `ctxmodule/llm.py` 的 `MiniMaxClient`，把选材结果作为上下文交给模型，产出统一 diff（`transcript/feature.patch`） |
| **seekdb** | 存储工程资料或索引，实际查询结果用于构造任务上下文 | `ctxmodule/seekdb_store.py`：规格、代码、测试全部入 seekdb 表 `ctx_documents`；`pipeline.build_context()` 只从**数据库查询结果**取素材，不读文件系统 |
| **PowerContext** | 保存任务进展或验证结果，并在后续运行中读取、使用 | `ctxmodule/pc.py`：通过官方 HTTP API（`/v1/sources/content`、`/v1/memory/remember`、`/v1/context/prepare`）保存任务状态；模块重启后重新读回并用于后续处理 |

### 1.3 上下文选择方式

1. 规格文件按 `SPEC-xxx` 行解析为约束条目，存入 seekdb 的 `spec:active` 文档（固定 doc_id，保证重新导入时**替换**而不是新增）。
2. 代码文件与测试文件按相对路径存入 `code:<path>` / `test:<path>`。
3. 选材时用**真实 SQL 查询**（`content LIKE ?` + `kind IN (...)`）检索，再按任务要求组装上下文。
4. 上下文里每一条来源都带 `doc_id`，评审可以逐条回查数据库行。

---

## 2. 环境准备（材料 2 · 运行说明）

### 2.1 要求

| 项 | 要求 |
| --- | --- |
| 操作系统 | **Linux x86_64**（Windows 原生不支持；本机用 WSL Ubuntu 22.04+） |
| Python | **3.12** |
| 包管理 | `uv`（或 pip） |
| 数据库 | 无需另行部署：使用嵌入式 **pylibseekdb** |
| PowerContext | 需要一个 PowerContext checkout（含 `src/powercontext`，分支 `2026-competition` 或更新） |

### 2.2 安装

```bash
# 1) 取一个 PowerContext checkout（上游公开仓库，无需凭据）
git clone --branch 2026-competition https://github.com/oceanbase/powercontext.git ~/ob-product

# 2) 建环境并安装依赖
uv venv --python 3.12 ~/ob-venv
uv pip install --python ~/ob-venv/bin/python \
    -e "$HOME/ob-product[seekdb,cli,server]" pytest pytest-asyncio
```

### 2.3 初始化数据并执行验证样例

```bash
cd minimax
export PYTHONPATH="$HOME/ob-product/src:$PWD"

# 初始化：把规格、代码、测试导入 seekdb
python -m ctxmodule import \
    --project sample_project \
    --spec sample_project/specs/billing_filter_v2.md

# 执行样例：组装上下文（输出 JSON，含全部来源）
python -m ctxmodule context \
    --task-id TASK-BILL-001 \
    --task "实现 SPEC-BILL-001-F 要求的 status 过滤" \
    --require-spec SPEC-BILL-001-F \
    --require-spec SPEC-BILL-001-G \
    --require-spec SPEC-BILL-001-H
```

### 2.4 一键自测（六项必做项）

```bash
cd minimax
PRODUCT=$HOME/ob-product PYTHON=$HOME/ob-venv/bin/python ./run_selftest.sh
```

输出六行门禁结果；任一项失败时脚本返回非零退出码。

### 2.5 录制真实的 MiniMax 开发会话

仓库里随附的开发记录是**离线引导记录**（`mode: "bootstrap"`），仅用于让自测可以离线跑通。
提交前必须用你自己的 MiniMax 账号重新录制：

```bash
export MINIMAX_API_KEY=<你的 MiniMax API Key>
export MINIMAX_BASE_URL=https://api.minimaxi.com/v1     # 或 https://api.minimax.chat/v1
export MINIMAX_MODEL=MiniMax-M2
PYTHONPATH="$HOME/ob-product/src:$PWD" python scripts/record_session.py --live
```

录制会重写 `transcript/minimax_session.jsonl` 与 `transcript/feature.patch`，
并把**当时实际使用的上下文摘要**写入记录。门禁 2 会校验记录中的上下文摘要、
来源集合与 diff 摘要和当前仓库一致，且 `mode` 为 `live`。

### 2.6 重置

```bash
rm -rf .ctxmodule-data          # 删除本地 seekdb 与 PowerContext 数据目录
rm -f transcript/minimax_session.jsonl transcript/feature.patch
```

---

## 3. 验证样例（材料 3）

### 3.1 任务描述

> 在 `sample_project` 中实现规格 `SPEC-BILL-001-F` 要求的按状态过滤：
> `filter_records(..., status="paid")` 只保留 `status` 完全相等的记录；
> `status` 为仅关键字参数；多个条件取交集；保持输入顺序。

### 3.2 有效规格

| 条目 ID | 内容 | 所在文件 |
| --- | --- | --- |
| SPEC-BILL-001-A | 按 `min_amount` 过滤，`amount >= min_amount` | `sample_project/specs/billing_filter_v2.md` |
| SPEC-BILL-001-F | 按 `status` 过滤，仅保留完全相等的记录；未提供时不按状态过滤 | 同上 |
| SPEC-BILL-001-G | 多条件取交集 | 同上 |
| SPEC-BILL-001-H | `status` 必须是仅关键字参数 | 同上 |

### 3.3 初始数据

`sample_project/src/billing/records.py` 中的 `SAMPLE`：`r1(50,CNY,paid)`、`r2(120,USD,pending)`、
`r3(200,CNY,paid)`、`r4(20,USD,refunded)`。

### 3.4 操作步骤

1. `python -m ctxmodule import --project sample_project --spec sample_project/specs/billing_filter_v2.md`
2. `python -m ctxmodule context --task-id TASK-BILL-001 --task "..." --require-spec SPEC-BILL-001-F ...`
3. 把上下文交给 MiniMax，得到 `transcript/feature.patch`
4. 在 `sample_project` 上应用该补丁
5. `pytest tests/test_target.py` 与 `pytest tests/test_regression.py`

### 3.5 预期结果

| 步骤 | 预期 |
| --- | --- |
| 1 | seekdb 中 `ctx_documents` 有 ≥ 4 行，`kind` 覆盖 `spec` / `code` / `test` |
| 2 | 输出的 `sources` 含 `spec:billing_filter_v2.md`、`code:src/billing/filter.py`、`test:tests/test_target.py`；`spec.items` 含 SPEC-BILL-001-F/G/H |
| 3 | 生成统一 diff，仅改动 `src/billing/filter.py` |
| 4 | 补丁可应用（`git apply -p1`） |
| 5 | 修改前目标测试 **失败**（`TypeError: filter_records() got an unexpected keyword argument 'status'`）；修改后目标测试与回归测试 **全部通过** |

### 3.6 重置方法

见 2.6；`sample_project/src/billing/filter.py` 在仓库中保存的就是**修改前**快照，
重新克隆即可回到初始状态。

---

## 4. 六项必做项 ↔ 验收门禁对照

| 必做项 | 门禁 | 检查内容 |
| --- | --- | --- |
| 能够运行 | `verify/gate1_runnable.py` | 干净环境下初始化数据、启动模块、执行验证样例；产出不依赖未交付的本地文件 |
| MiniMax 实际参与 | `verify/gate2_minimax_used.py` | 开发记录含任务、上下文摘要、来源集合；与提交的 diff 摘要一致；`mode == "live"` |
| 上下文正确 | `verify/gate3_context_correct.py` | 输出含样例规定的规格 / 代码 / 测试来源；规格更新并重新导入后输出使用新内容 |
| 数据库实际参与 | `verify/gate4_database_used.py` | 工程资料确实存入 seekdb；上下文的每条来源都能在数据库行中逐字回查；检索由 SQL 查询驱动 |
| 状态能够复用 | `verify/gate5_state_reused.py` | 从空状态保存任务记录 → **重启 PowerContext Server** → 重新读回并用于后续处理 |
| 代码修改有效 | `verify/gate6_code_change_effective.py` | 修改前目标测试因目标行为缺失而失败（且非环境原因）→ 应用补丁后通过；回归测试通过；日志记录命令与退出码 |

---

## 5. 已知限制

1. `transcript/minimax_session.jsonl` 随仓库提供的是**离线引导记录**，提交前必须用
   `scripts/record_session.py --live` 重新录制，否则门禁 2 不会通过。
2. `sample_project` 是随包提供的最小业务工程，用于让验收在干净环境中可复现；
   如需换成自己的业务工程，替换 `sample_project/` 并同步更新 `scripts/record_session.py`
   中的任务描述与规格条目即可。
3. 自测在 Linux 上运行；Windows 上可用 WSL（`wsl -e bash -lc "..."`）。
4. 模块不访问公网即可完成除 MiniMax 调用之外的全部流程；官方测试不需要模型 API Key。
5. seekdb 数据目录与 `POWERCONTEXT_HOME` 必须位于 **Linux 本地文件系统**；放在 `/mnt/<盘符>`
   （WSL 挂载的 Windows 盘）上会报 `seekdb_open failed: code=-1`。详见 6.2。
6. `artifacts/` 随仓库提交，是材料 4 / 5 的一部分；重新录制 live 会话后请一并重跑
   `python scripts/dump_usage.py` 刷新技术使用记录。

---

## 6. 六份材料对照

| 材料 | 位置 |
| --- | --- |
| 1 完整源码 | 本目录（`ctxmodule/`、`sample_project/`、`verify/`、`scripts/`） |
| 2 运行说明 | 本文件第 2 节 |
| 3 验证样例 | 本文件第 3 节 + `materials/03_verification_sample.md` |
| 4 代码与测试 | `materials/04_code_and_tests.md`；修改前/后快照 `sample_project/src/billing/filter.py` 与 `transcript/after/src/billing/filter.py`；diff `transcript/feature.patch`；测试 `sample_project/tests/`；**运行日志 `artifacts/*.log`** |
| 5 技术使用记录 | `materials/05_tech_usage.md`；**MiniMax 开发记录 `transcript/minimax_session.jsonl`**；**数据库查询记录 `artifacts/usage/seekdb-queries.txt`**；**PowerContext 状态写入与复用记录 `artifacts/usage/powercontext-state.txt`**；MiniMax 汇总 `artifacts/usage/minimax-usage.json` |
| 6 一页技术说明 | 本文件第 1 节 |

### 6.1 `artifacts/` 是提交的一部分

`artifacts/` 里的内容**随仓库提交**（`.gitignore` 只排除本地工作目录 `.ctxmodule-data/`），
因为官方对材料 4 和材料 5 明确要求"运行日志"和"技术使用记录"。

| 文件 | 内容 | 重新生成 |
| --- | --- | --- |
| `artifacts/target-tests-before.log` | 修改前目标测试的**命令、退出码、stdout/stderr、代码版本** | `pytest -q tests/test_target.py`（修改前） |
| `artifacts/target-tests-after.log` | 修改后目标测试日志（6 passed） | `pytest -q tests/test_target.py`（修改后） |
| `artifacts/regression-tests-after.log` | 回归测试日志（7 passed） | `pytest -q tests/test_regression.py` |
| `artifacts/usage/seekdb-queries.txt` | seekdb 实际执行的查询与命中行 | `python scripts/dump_usage.py` |
| `artifacts/usage/powercontext-state.txt` | PowerContext 状态**写入 → 重启 → 读回**全过程 | `python scripts/dump_usage.py` |
| `artifacts/usage/minimax-usage.json` | MiniMax 开发记录汇总 | `python scripts/dump_usage.py` |

每条日志都含 `command` / `exit_code` / `code_version`，满足官方"测试日志需记录命令、退出码和对应代码版本"的要求。

### 6.2 数据目录必须放在本地 Linux 文件系统

`seekdb` 的数据目录和 `POWERCONTEXT_HOME` **不能放在 `/mnt/<盘符>`**（WSL 里的 Windows 盘）：
seekdb 会报 `seekdb_open failed: code=-1`，SQLite 也无法加锁。

```bash
export CTXMODULE_SEEKDB_DIR=/tmp/ctxmodule-seekdb        # 或任意 Linux 本地路径
export POWERCONTEXT_HOME=/tmp/ctxmodule-powercontext
```

`scripts/dump_usage.py` 默认就会用临时目录（`tempfile.mkdtemp`），因此开箱即用；
只有当你显式设置了指向 `/mnt/...` 的环境变量时才会踩这个坑。


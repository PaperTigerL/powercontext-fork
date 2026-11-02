# 验证样例 · MemCoach

本文件是提测时的**逐条自检清单**。每条样例对应题面的一项验收要求，
格式统一为「操作步骤 → 预期输出 → 判定标准（通过/不通过）」。

约定：

- 后端默认端口 `8899`；若被占用，示例里的 `PORT=9000` 可替换。
- 实时模式需要 PowerContext Server（地址与 `scope_id` 见 `app/README.md` 第 2.2 节）。
- 下列命令在 Windows PowerShell 与 Linux/macOS 下都能跑；`curl` 在 Windows 上用 `curl.exe`。

---

## V1 · 未登录也能打开网站（对应题面「基础验收」第 1 条）

**操作步骤**

1. 用一个**没有登录任何账号**的浏览器（或无痕窗口）打开 Qoder Sites 给出的网址。
2. 页面应完整渲染出五个面板：录入学习卡片 / 记忆库 / 检索记忆 / 复习会话 / 学习足迹。

**预期输出**

- 页面正常加载，样式完整，没有 403 / 登录跳转 / 「请先登录」。
- 右上角徽章显示「演示模式（内置数据）」或「实时模式 · PowerContext」之一。

**判定标准**

- 通过：未登录状态下网站可打开且完整可用。
- 不通过：出现登录墙、403 或白屏 → 回到 `README.md` 第 6 节检查「Qoder Sites 可见范围」。

---

## V2 · 零配置演示模式开箱可交互（对应题面「基础验收」第 2 条）

**操作步骤**

1. 本地执行：

   ```bash
   cd qoder/app
   node server.js
   ```

2. 浏览器打开 `http://127.0.0.1:8899`。
3. 在「① 录入学习卡片」里填：
   - 标题：`幂等键要带租户维度`
   - 类型：`踩坑`
   - 要点：`同一幂等键换业务参数会污染旧结果` / `跨租户要加租户前缀`
   - 标签：`幂等, 后端`
   - 出处：`自测记录`
4. 点「保存到长期记忆」。

**预期输出**

- 「② 记忆库」里立刻多出这条卡片，并显示：
  `entry_id=demo-entry-N`、`entry_version_id=demo-entry-N@v1`、`state=active`。
- 记忆库初始就有 5 张内置样例卡片（演示模式才有；真实 PowerContext 的新 scope 是空的）。
- 右上角徽章是「演示模式（内置数据）」。

**判定标准**

- 通过：无需安装任何依赖、无需配置任何环境变量，保存后卡片立即出现在记忆库里。
- 不通过：启动报错或保存无反应 → 检查 Node 版本是否 ≥ 18。

---

## V3 · 实时模式真实写入 PowerContext（对应题面「技术结合要求」）

**操作步骤**

1. 启动 PowerContext Server，准备好 `scope_id`（见 `app/README.md` 第 2.2 节）。
2. 启动本应用：

   ```bash
   cd qoder/app
   export POWERCONTEXT_URL=http://127.0.0.1:8000
   export POWERCONTEXT_SCOPE_ID=<你的 scope_id>
   node server.js
   ```

3. 保存一张卡片（与 V2 相同的表单）。
4. 直接查 PowerContext：

   ```bash
   curl -s -X POST -H "Content-Type: application/json" \
     -d "{\"scope_id\":\"$POWERCONTEXT_SCOPE_ID\"}" \
     "$POWERCONTEXT_URL/v1/memory/entries/list"
   ```

**预期输出**

- 本应用返回 `{"entry":{"citation":{"entry_id":"..."},"kind":"study-card","state":"active",...}}`。
- 上一步 curl 的返回里能看到**刚保存的那条** `kind=study-card` 条目，正文形如
  `card=幂等键要带租户维度 | type=pitfall | points=... | tags=... | src=...`。
- `GET /api/health` 里 `mode` 是 `live`，`powercontext.scope_id` 非空。

**判定标准**

- 通过：卡片真的落在 PowerContext 的 Memory 里，且**不是**只写在浏览器本地。
- 不通过：只有前端能看到、PowerContext 查不到 → 说明没走实时模式，检查 `MEMCOACH_MODE` 与环境变量。

> 这条是「不能只是装个组件测连通」的关键证据：数据真的落在 PowerContext 里。

---

## V4 · 检索 → 复用 → 用户可见（对应题面「技术结合要求」与「用户可见效果」）

**操作步骤**

1. 在实时模式下用 V3 的卡片标题做一次检索：

   ```bash
   curl -s -X POST -H "Content-Type: application/json" \
     -d '{"query":"幂等键","limit":5}' http://127.0.0.1:8899/api/search
   ```

2. 在网页「③ 检索记忆」输入 `幂等键`，点「检索」。
3. 在「④ 复习会话」输入同一个词，点「开始复习」。

**预期输出**

- 检索结果里出现 V3 保存的那条，`score` 有值、`matched_by` 是 `fts`（或 `hybrid`/`vector`），
  并带 `entry_id`。
- 复习会话里的题目直接引用了那条记忆的要点（例如「围绕「幂等键要带租户维度」：同一幂等键换业务参数会污染旧结果 —— 这条你还记得吗？」），
  并且标注「来源记忆条目 #<entry_id>」与检索得分。

**判定标准**

- 通过：复习题的内容**来自记忆条目正文**，页面上能同时看到来源 `entry_id` 与检索得分；
  关闭浏览器再打开重做，检索仍命中同一条。
- 不通过：复习题是随机模板、与记忆内容无关 → 说明没有真正走检索复用。

---

## V5 · 掌握度闭环：复用结果反过来影响后续使用（对应题面「真正发挥作用」）

**操作步骤**

1. 在复习会话里，对 V3 的卡片点「需加强」，备注写 `只记住了结论`。
2. 点「刷新」看「② 记忆库」。
3. 不带主题、直接点「开始复习」（或换一个宽泛主题）。

**预期输出**

- 记忆库里多了一条 `kind=review-outcome` 的条目，正文形如
  `review=<entry_id> | verdict=weak | note=只记住了结论 | at=<ISO 时间>`。
- 该卡片在复习会话里显示「上次结果：需加强（<日期>） · 只记住了结论」。
- 「⑤ 学习足迹」里「需加强」计数 +1。
- 带主题复习时，该卡片排在同组卡片**前面**（需加强 > 未复习 > 已掌握）。

**判定步骤**：对照 `POST /v1/memory/entries/list` 的返回，确认 `review-outcome` 条目真实存在于 PowerContext。

**判定标准**

- 通过：一次复习结果被写进长期记忆，并在下一次复习中改变了排序与展示。
- 不通过：掌握度只存在浏览器内存里，刷新即丢 → 说明没写进 PowerContext。

---

## V6 · PowerContext 不可用时清晰报错而非崩溃

**操作步骤**

```bash
cd qoder/app
MEMCOACH_MODE=live POWERCONTEXT_URL=http://127.0.0.1:59999 POWERCONTEXT_SCOPE_ID=demo node server.js
# 另开一个终端
curl -s -w "\nHTTP=%{http_code}\n" http://127.0.0.1:8899/api/cards
```

**预期输出**

- 返回 `502`，报文形如
  `{"error":{"code":"powercontext_unreachable","message":"无法连接 PowerContext Server（http://127.0.0.1:59999/v1/memory/entries/list）：..."}}`。
- 进程仍在运行，再打一次 `/api/health` 依然是 `200`。
- 去掉 `POWERCONTEXT_URL` 后启动，则 `/api/cards` 返回 `503` +
  `powercontext_not_configured`，并提示用 `dify/scripts/init_scope.py` 或 `POWERCONTEXT_AUTO_SCOPE=1`。

**判定标准**

- 通过：两种缺配置/连不上场景都返回结构化错误，且服务不退出。
- 不通过：进程崩溃、返回 HTML 堆栈页、或无限挂起。

---

## V7 · 评审按运行说明从零跑通（对应题面「评审能按运行说明跑通主要功能」）

**操作步骤**

1. 找一个**没参与开发**的人（或另一台机器），只给 `qoder/README.md` 的「运行说明」与「提测提交清单」两节。
2. 按 `qoder/README.md` 第 4 节执行；再执行：

   ```bash
   cd qoder/app
   node scripts/selftest.js
   ```

**预期输出**

- `node server.js` 启动成功并打印模式与 PowerContext 地址。
- `node scripts/selftest.js` 输出 **7 个环节 15 个断言全部 PASS**，退出码 0。

**判定标准**

- 通过：不依赖任何口头补充，别人按文档就能跑通主要功能。
- 不通过：文档缺步骤、命令与实际不一致 → 修订 `qoder/README.md` 后重测。

---

## V8 · Qoder 开发记录可核对（对应题面「Qoder 开发过程记录」与「基础验收」第 3 条）

**操作步骤**

1. 按 `qoder/PROMPT.md` 的五个阶段顺序在 Qoder 中推进，每阶段结束都让 Qoder 输出「本阶段小结」。
2. 把各阶段小结与关键对话整理进 `qoder/DEVLOG.md`（模板见 `qoder/DEVLOG.template.md`）。
3. 核对记录里能对应上：需求拆解 → 数据模型与接口设计 → 编码 → 调试与自测 → 部署发布，各阶段都有 Qoder 的产出与验证命令。

**预期输出**

- `qoder/DEVLOG.md` 里每一阶段都有：Qoder 做了什么、改了哪些文件、跑了什么命令、结果是什么。
- 记录中的接口名、字段名与 `qoder/app/src/powerContextClient.js` 中的实际调用一致。

**判定标准**

- 通过：评审能看出主要开发工作确实在 Qoder 中完成，且各阶段有可验证的产出。
- 不通过：只有最终结果没有过程 → 补齐 `DEVLOG.md` 并保留 Qoder 会话记录。

---

## 附：curl 速查

```bash
# 健康检查
curl -s http://127.0.0.1:8899/api/health

# 记忆库（对应 entries/list）
curl -s http://127.0.0.1:8899/api/cards

# 写入一张卡片（对应 remember）
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"title":"幂等键要带租户维度","type":"pitfall","points":["同一幂等键换业务参数会污染旧结果"],"tags":["幂等"],"source":"自测"}' \
  http://127.0.0.1:8899/api/cards

# 检索（对应 search）
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"query":"幂等键","limit":5}' http://127.0.0.1:8899/api/search

# 复习会话 / 记录掌握度
curl -s -X POST -H "Content-Type: application/json" -d '{"query":"幂等键"}' http://127.0.0.1:8899/api/review/session
curl -s -X POST -H "Content-Type: application/json" -d '{"cardId":"<entry_id>","verdict":"weak","note":"只记住了结论"}' http://127.0.0.1:8899/api/review/answer

# 统计
curl -s http://127.0.0.1:8899/api/stats
```

## 附：这些样例的自测状态（诚实标注）

| 样例 | 本次是否实测 | 说明 |
| --- | --- | --- |
| V1 | ❌ 未实测 | 没有真实 Qoder Sites 网址，需要参赛者发布后自测 |
| V2 | ✅ 已实测 | 演示模式全流程在本地跑通，自检脚本 15/15 PASS |
| V3 | ⚠️ 部分实测 | 写入链路对着 PowerContext **契约桩**跑通；**未**与真实 PowerContext Server 联调 |
| V4 | ⚠️ 部分实测 | 检索与复用逻辑对着契约桩跑通；**未**在真实集群验证检索命中效果 |
| V5 | ⚠️ 部分实测 | 掌握度闭环对着契约桩跑通；真实集群未验证 |
| V6 | ✅ 已实测 | 缺配置（503）与连不上（502）两种情况都实测过，服务均未崩溃 |
| V7 | ✅ 部分实测 | 自检脚本实测通过；「换人按文档从零跑通」需要参赛者复核 |
| V8 | ❌ 未实测 | 需要在真实 Qoder 客户端里推进五个阶段后整理 |

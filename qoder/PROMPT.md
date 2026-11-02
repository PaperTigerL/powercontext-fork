# 分阶段提示词 · MemCoach（可直接粘贴给 Qoder）

**用法**：按 1 → 5 的顺序，逐段把下面的「提示词正文」整段粘贴给 Qoder。
每段结束，Qoder 都会输出「本阶段小结」——**请立刻把小结复制到 `qoder/DEVLOG.md`**（模板见 `DEVLOG.template.md`），
这就是题面要求的「Qoder 开发过程记录」。

> 骨架已经在仓库里了（`qoder/app/`），Qoder 的任务是**在骨架上继续开发**，
> 不是从零重写。提示词里已经写明这一点，避免 Qoder 推翻已有实现。

---

## 阶段 1 · 需求拆解与架构设计

**提示词正文（整段复制）：**

```text
你现在在仓库的 qoder/ 目录下工作，当前分支是 2026-competition-ecosystem。
请先阅读 qoder/README.md 与 qoder/app/README.md，了解参赛要求与现有骨架，
然后做「需求拆解与架构设计」，先不要改代码。

项目：MemCoach（记忆复习教练）——把学习卡片存进 PowerContext 长期记忆，
之后按主题检索记忆、用记忆内容出题复习、记录掌握度，掌握度再影响下次的复习排序。

本阶段请交付：
1. 一份功能清单，标注哪些功能已由骨架实现、哪些需要你补齐；优先级从高到低。
2. 一份数据流说明：用户输入 → 哪个接口 → PowerContext 的哪个端点 → 回来后渲染到哪个面板。
   必须能画出「写入 remember → 检索 search → 复用出题 → 用户可见效果」这条闭环。
3. 一份技术选型说明：为什么后端用 Node 原生 http + 原生 fetch、前端不用框架，
   以及这样选对「零依赖、可被评审一键跑通」的影响。
4. 一份风险清单：至少覆盖 PowerContext 不可用、检索无命中、scope 隔离、静态部署与后端分离。

约束：
- 必须复用骨架已有的代码结构（src/ 与 public/），不要另起炉灶。
- 记忆相关的接口必须严格使用仓库里已验证的路径与字段：
  POST /v1/memory/remember、POST /v1/memory/search、POST /v1/memory/entries/list，
  请求体字段是 scope_id / kind / text / reason 与 scope_id / query / limit / mode，
  响应结构见 src/powerContextStore.js。
  不要发明新的路径或参数名；不确定时去读 openapi/powercontext.yaml 与 dify/scripts/verify_memory_api.py。
- 全部用中文写文档与注释。

完成标准：四份产出都落到 qoder/DEVLOG.md 的「阶段 1」小节里，代码零改动。
本阶段结束时，请输出一段「本阶段小结」，包含：
你读了哪些文件、得出了什么结论、接下来打算先做哪三件事。
```

**验收标准**

- `qoder/DEVLOG.md` 的阶段 1 小节有四份产出，且数据流里出现了 remember / search / entries-list 三个端点。
- `git diff --stat`（或编辑器变更列表）显示 `qoder/app/` 下代码未被改动。

**建议的验收命令**

```bash
node --check qoder/app/server.js && node --check qoder/app/src/routes.js
```

---

## 阶段 2 · 数据模型与 PowerContext 接口设计

**提示词正文（整段复制）：**

```text
继续 MemCoach 项目，现在做「数据模型与 PowerContext 接口设计」，可以开始写代码，
但只允许改 qoder/app/public/domain.js、qoder/app/src/ 下的文件，
以及在 qoder/DEVLOG.md 里追加内容。

本阶段请交付：
1. 记忆条目正文格式的正式定义，写进 qoder/app/public/domain.js 的注释与 DEVLOG.md。
   现有格式是：
     card=<标题> | type=<concept|decision|pitfall|fact> | points=<要点1> ; <要点2> | tags=<t1,t2> | src=<出处>
     review=<被复习的 entry_id> | verdict=<strong|weak> | note=<备注> | at=<ISO 时间>
   请检查它是否满足：能被全文检索稳定命中、能被人直接读懂、能解析回结构化数据、
   字段分隔符不会与用户输入冲突。必要时给出改进并同步更新格式化/解析函数。
2. 一个「MemoryStore」接口定义（list / remember / search 三个方法），
   说明它必须同时被实时实现（src/powerContextStore.js）与演示实现（public/demo-store.js）遵守，
   并保证两者的返回结构逐字段对齐。
3. PowerContext 错误处理约定：把上游的 401/403/404/409/422/5xx 映射成本应用的
   HTTP 状态与 error code，写进 src/errors.js 的注释与 DEVLOG.md。
4. 明确 scope 语义：所有读写绑定同一个 scope_id；scope 是数据分区键而不是访问控制；
   多用户应当各自使用独立 scope。

约束：
- 接口路径、请求字段、响应字段必须与 openapi/powercontext.yaml 一致；
  写完用 dify/scripts/verify_memory_api.py 的用法对照检查一次。
- 记忆正文不得超过 8192 个 UTF-8 字节（NFC 规范化并 trim 之后），超长要返回 422。
- 不要引入任何第三方依赖。
- 全部用中文写注释与文档。

完成标准：domain.js 的注释里能直接看出条目格式与 store 契约；
src/ 下有清晰的分层（客户端 / store / 路由 / 配置 / 错误）。

本阶段结束时，请输出一段「本阶段小结」，包含：
你改动了哪些文件与函数、条目格式与接口契定的最终版本、
以及你如何确认这些字段名与仓库里的契约一致。
```

**验收标准**

- `qoder/DEVLOG.md` 阶段 2 小节写清了条目格式、store 契约、错误映射表、scope 语义。
- `src/powerContextClient.js` 里的路径与字段名与 `openapi/powercontext.yaml` 逐字一致。

**建议的验收命令**

```bash
cd qoder/app
npm run check
```

---

## 阶段 3 · 编码

**提示词正文（整段复制）：**

```text
继续 MemCoach 项目，现在做「编码」阶段。按阶段 2 定下的设计补齐功能，
把主要工作量放在真正体现 PowerContext 作用的地方。

必须做（按优先级）：
1. 让「记忆被保存并在后续使用中被复用」在页面上肉眼可见：
   - 复习题必须来自记忆条目正文（用条目的 points 派生），并标注来源 entry_id 与检索得分；
   - 掌握度（已掌握 / 需加强 / 未复习）要改变复习会话的排序；
   - 记忆库面板要显示 citation、version、state，让评审看到这是 PowerContext 的条目而不是本地数组。
2. 后端与前端共用同一套领域逻辑（public/domain.js），保证演示模式与实时模式行为一致；
   演示模式不得走另一套简化逻辑。
3. 输入校验与错误提示：标题为空、检索词为空、正文超长（>8192 UTF-8 字节）、
   verdict 非法，都要返回结构化错误，而不是 500 或静默失败。
4. 可访问性与可读性：页面在 1280 宽下不横向滚动；关键状态（模式徽章、条目 id、得分）有文字说明，
   不要只用颜色区分。
5. 如需补充测试或脚本，放到 qoder/app/scripts/ 下，保持零依赖。

约束：
- 只能改 qoder/ 目录下的文件。
- 不引入第三方依赖；不得新增需要联网安装的重量级依赖。
- 记忆相关调用一律走 src/powerContextClient.js，不要在路由里直接 fetch。
- 中文注释，简洁，不写废话注释。
- 不要新增 TODO / 待实现 / 空函数占位。

完成标准：qoder/app 下 node server.js 能起服务，前端五个面板都能真实交互，
演示模式下不依赖任何后端即可完整走通「录入 → 记忆库 → 检索 → 出题 → 记掌握度 → 排序变化」。

本阶段结束时，请输出一段「本阶段小结」，包含：
按文件列出你做了什么、每个改动解决什么问题、你认为最容易出错的地方在哪。
```

**验收标准**

- 演示模式下完整闭环可走通；没有 TODO / 空壳函数。
- `qoder/app/` 下没有新增第三方依赖。

**建议的验收命令**

```bash
cd qoder/app
npm run check
node server.js
# 另开终端
node scripts/selftest.js
```

---

## 阶段 4 · 调试与自测

**提示词正文（整段复制）：**

```text
继续 MemCoach 项目，现在做「调试与自测」阶段。目标是让评审按运行说明就能跑通，
并且让「PowerContext 真的在起作用」这件事有可复现的证据。

请完成：
1. 按 qoder/VERIFICATION.md 的 V1~V8 逐条自测，把每条的结果（通过/不通过、实际输出摘要）
   写进 qoder/DEVLOG.md 的「阶段 4」小节。V1（Qoder Sites）与 V8（开发记录）现在还做不了，
   请明确标注「待发布后补测」，不要写成已通过。
2. 补齐 scripts/selftest.js 的覆盖：确保它能同时验证
   「写入 → entries/list 读回 → search 命中同一条 → 复习题目引用该条要点 →
   记录掌握度 → 统计与卡片掌握度回显」这条链，每步都有 PASS/FAIL 断言，失败时退出码非 0。
3. 造出并记录至少 2 个真实故障场景的实测输出：
   - 未配置 POWERCONTEXT_URL/POWERCONTEXT_SCOPE_ID 且 MEMCOACH_MODE=live；
   - 配置了地址但服务连不上。
   确认两者都返回结构化错误、进程不退出。
4. 写一段「如果 PowerContext 不可用会怎样」的说明进 DEVLOG.md，
   明确演示模式能兜住哪些场景、兜不住哪些场景。

约束：
- 只改 qoder/ 目录下的文件。
- 不得把「对着契约桩跑通」写成「已与真实 PowerContext 联调」；实测与未实测必须分开写。
- 保留失败现场的真实报错文本，不要润色成模糊描述。

完成标准：node scripts/selftest.js 在演示模式下全绿；
两个故障场景都有实测报错记录；DEVLOG.md 的阶段 4 小节逐条对应 VERIFICATION.md。

本阶段结束时，请输出一段「本阶段小结」，包含：
跑过的命令与结果摘要、修掉了哪些问题、哪些问题仍然存在且为什么。
```

**验收标准**

- `node scripts/selftest.js` 退出码 0。
- DEVLOG.md 阶段 4 小节里，实测项与未实测项被清楚分开。

**建议的验收命令**

```bash
cd qoder/app
node scripts/selftest.js
MEMCOACH_MODE=live node server.js   # 另一个终端里 curl /api/cards 看 503/502
```

---

## 阶段 5 · 部署与 Qoder Sites 发布

**提示词正文（整段复制）：**

```text
继续 MemCoach 项目，现在做「部署与 Qoder Sites 发布」阶段。

目标：让评审在**未登录状态**下打开网站就能体验到完整交互。

请完成：
1. 确认前端可以被静态托管：
   - qoder/app/public/ 下的 index.html、styles.css、app.js、domain.js、demo-data.js、
     demo-store.js 就是完整的静态站点，路径必须是相对路径（用 ./ 而不是 /），
     这样放在任意子目录下都能打开；
   - 打开 static 站点时若检测不到后端，前端会自动切到内置演示模式，
     请确认这个兜底路径真的可用（断网或后端地址填错时都要能用）。
2. 在 Qoder 里完成发布准备：
   - 给出「发布根目录应该选 qoder/app/public」的明确结论与理由；
   - 如果 Qoder Sites 需要构建产物，说明为什么本项目不需要构建（纯静态、零依赖）；
   - 确认发布产物里不含任何 token、任何本地绝对路径、任何 node_modules。
3. 检查 Qoder Sites 的可见范围设置：必须是「任何人都可访问」（公开访问）。
   企业版账号无法设置公开访问，必须用个人账号——这一点要写进 DEVLOG.md 的提醒。
4. 写出发布后的验证步骤（对应 qoder/VERIFICATION.md 的 V1 与 V7），放进 DEVLOG.md。

约束：
- 不要把 PowerContext 的 token 写进任何前端文件；token 只能留在服务端环境变量里。
  如果评审要在公网演示实时模式，说明后端需要另行部署到公网可达地址，
  并在 DEVLOG.md 里写清楚这一点（静态站点 + 远端后端 + 填「后端地址」的用法）。
- 不要为了发布去修改记忆接口的语义。

完成标准：给出一份「发布清单」，包含发布根目录、可见范围设置、发布后要跑的验证命令，
以及发布网址填到 qoder/README.md 提测清单的哪个字段。

本阶段结束时，请输出一段「本阶段小结」，包含：
发布配置、可见范围设置、发布网址、以及发布后还要补做的验证项。
```

**验收标准**

- DEVLOG.md 阶段 5 小节包含发布根目录、可见范围、验证步骤。
- 静态产物里 grep 不到 token 之类的敏感串：

  ```bash
  grep -rn "Bearer\|POWERCONTEXT_TOKEN=" qoder/app/public || echo "public 下没有 token 痕迹"
  ```

---

## 附：给参赛者的两点提醒

1. **别把提示词一次性全粘完**。五个阶段是递进的：上一阶段的产出（条目格式、接口契约、阶段小结）
   是下一阶段的输入。一次性粘完会导致 Qoder 没有产出可核对的中间过程，
   而题面明确要求保留「需求拆解、编码、调试各环节 Qoder 做了什么」。
2. **每阶段结束先存小结再进下一阶段**。`DEVLOG.md` 是评审要核对的材料，
   事后再回忆补写通常补不完整。

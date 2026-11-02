# 魔搭社区赛题交付包：财报证据页检索 Skill

本目录是 OceanBase 大赛「魔搭社区」生态赛题的可上传交付物：一个自写的 Agent Skill，
打包后上传到魔搭社区技能中心，回填 **Skill 网址或编号**。

- **Skill 名称**：财报证据页检索
- **Skill 标识**：`financial-evidence-page-finder`（只允许小写字母、数字、连字符，创建后不可修改）
- **分类**：文档处理（`doc-processing`）
- **一句话**：给定一份财报 PDF 和一个财务问题，返回**可回查的证据页**——物理页码 + 命中词 + 原文片段。

---

## 一、这个 Skill 能做什么

输入一份 10-K / 10-Q / 年报 PDF 和一个自然语言财务问题，输出排序后的证据页：

| 能力 | 说明 |
| --- | --- |
| 全文逐页解析 | 用 pypdf 抽取**全部物理页**文本，页码从 1 开始，含空白页 |
| 词法证据打分 | 按问题词、短语、领域别名的**覆盖度**排序，而不是词频排序 |
| 同义表述识别 | `revenue` ↔ `net sales`/`total revenues`，`capex` ↔ `purchases of property, plant and equipment` 等 |
| 报表类型提示 | `income statement` / `balance sheet` / `cash flow`，可用 `--statement` 强制指定 |
| 可回查引用 | 同时输出文件 SHA-256 与物理页码，保证引用的是同一份文件的同一页 |
| 原文片段 | 摘出该页中承载证据的若干行，命中处用 `[[ ]]` 标出 |

明确**不做**的事：不包含 OCR（扫描件请先 OCR）、不做数值计算、不生成最终答案、不跨文档检索。

## 二、目录结构

```
modelscope/
├── README.md                      本文件
├── SKILL_UPLOAD_NOTES.md          发布时可直接粘贴的字段清单
├── pack_skill.py                  打包与前置校验脚本（校验魔搭社区的归档规则）
└── financial-evidence-page-finder/
    ├── SKILL.md                   Skill 定义（YAML frontmatter + 使用说明）
    ├── requirements.txt           依赖（pypdf）
    ├── scripts/
    │   ├── find_evidence.py       证据页检索脚本
    │   └── make_sample_pdf.py     生成极小合成样例年报（零依赖，用于离线复现）
    ├── references/
    │   ├── scoring.md             打分模型、权重与同义扩展表
    │   └── reproduction.md        三种复现方式
    └── examples/
        └── sample_questions.md    示例问题与预期结果
```

## 三、依赖与安装

- Python 3.9 及以上
- 唯一的第三方依赖：`pypdf`（PDF 文本抽取）；纯文本输入模式下**零依赖**

```bash
cd financial-evidence-page-finder
pip install -r requirements.txt
```

## 四、典型使用示例

```bash
# 1) 生成极小的合成样例年报（可选，用于离线自测）
python scripts/make_sample_pdf.py --out /tmp/sample_annual_report.pdf

# 2) 给定财报 PDF 与财务问题，返回证据页
python scripts/find_evidence.py \
  --pdf /path/to/report.pdf \
  --question "What was the company's net sales in fiscal 2023?" \
  --topk 5
```

Markdown 输出（节选）：

```
| 排名 | 物理页码 | 得分 | 命中词 | 片段 |
| --- | --- | --- | --- | --- |
| 1 | 3 | 16.4129 | 2023, net, sales, net sales | [[Net sales]]  12,480  11,020  9,745  Cost of [[sales]] ... |
```

其他常用参数：

```bash
--topk 10                 # 返回更多候选页
--statement balance       # 强制偏向资产负债表
--format json             # 机器可读输出
--out result.json         # 写入文件
--text report.txt         # 纯文本财报（页间用 \f 分隔），无需 pypdf
```

完整参数见 `financial-evidence-page-finder/SKILL.md`。

## 五、效果说明（本机实测）

实测环境：Windows 11，Python 3.12.7，pypdf 6.20.1，无网络访问。

### 实测 1：合成样例（6 页虚构年报）

```bash
python scripts/make_sample_pdf.py --out sample_annual_report.pdf
python scripts/find_evidence.py --pdf sample_annual_report.pdf \
  --question "What was the company's net sales in fiscal 2023?" --topk 3
```

输出摘要：第一名是**第 3 页**（`CONSOLIDATED STATEMENTS OF OPERATIONS`），得分 16.4129，
命中 `net sales`，片段摘出 `Net sales` 行。

```bash
python scripts/find_evidence.py --pdf sample_annual_report.pdf \
  --question "What were the company's capital expenditures in fiscal 2023?" --topk 3
```

输出摘要：第 5 页（现金流量表，得分 46.7172）与第 6 页（`NOTE 8`，得分 27.3818）排在前两名。
问题里写的 `capital expenditures` 与财报里写的 `Purchases of property, plant and equipment`
通过同义扩展对上。

```bash
python scripts/find_evidence.py --pdf sample_annual_report.pdf \
  --question "How much total current assets did the company report at the end of fiscal 2023?" \
  --statement balance --topk 3
```

输出摘要：第 4 页（资产负债表）得分 73.0218，远高于其余页面，片段摘出 `Total current assets` 行。

### 实测 2：真实 503 页 10-K（赛题四公开样例）

样例来源：PowerContext 赛题四 `source-03-pdf-retrieval` 的公开自测集
（FinanceBench，CC BY-NC 4.0，**不随本 Skill 分发**，按需自行下载）。

```bash
python scripts/find_evidence.py --pdf PEPSICO_2022_10K.pdf \
  --question "What are the geographies that Pepsico primarily operates in as of FY2022?" --topk 5
```

输出摘要：

- 解析到 **503** 个物理页；工具算出的 SHA-256 与公开样例登记值**完全一致**
  （`7d8a9f3374e429c58f101319e2da8a0e601a89859e1e4f6854163dd5f8ce6b47`）；
- 第一名第 5 页（得分 105.6547），片段正是 Item 1 Business 里列举
  Latin America / Europe / Africa, Middle East and South Asia / Asia Pacific 的那一段；
- `geographies` 别名被自动展开成各大区名称，这是该问题命中正确的关键。

```bash
python scripts/find_evidence.py --pdf PEPSICO_2022_10K.pdf \
  --question "What is the FY2022 unadjusted EBITDA less capex for PepsiCo? Define unadjusted EBITDA as unadjusted operating income + depreciation and amortization from the cash flow statement." --topk 5
```

输出摘要：第 64 页（`Consolidated Statement of Cash Flows`，得分 223.2688，片段含
`Depreciation and amortization 2,763`）与第 54 页（MD&A，得分 177.1302，片段含
`Capital spending (5,207)`）排在最前——这两页正是取该问题所需两个数的地方。

另两个公开问题的命中情况（实测，前 4 名）：

| 问题 | 命中页（实测，按得分排序） |
| --- | --- |
| 有无重大未决诉讼 | 第 4 页（`Private Securities Litigation Reform Act`，属于 `litigation` 一词的误命中）、第 25、24、23 页（法律风险因素正文，`legal` 别名展开为 `legal proceedings`） |
| 利润表中列示的重组费用 | 第 105 页（重组相关附注）、第 103 页（累计其他综合损失重分类表）、第 62 页（`Consolidated Statement of Income`）、第 495 页 |

这两个问题说明了两点：一是 `legal`、`restructuring` 这类概念别名确实把相关页面带了出来；
二是词法检索会有误命中，工具把命中词原样列出（`matched_terms` / `matched_aliases`），
正是为了让使用者一眼看出某页是**因为哪个词**被选中的。最终引用前仍需打开原页核对。

### 实测 3：错误处理

| 场景 | 行为 |
| --- | --- |
| 文件不存在 | `error: cannot read '...': No such file or directory`，退出码 2 |
| 文件不是 PDF | `error: '...' is not a readable PDF: ...`，退出码 2 |
| 同时给 `--pdf` 与 `--text` | 报参数错误并打印用法，退出码 2 |
| 有命中 / 无命中 | 退出码 0 / 1 |

## 六、上传到魔搭社区（操作指引）

先注册并登录魔搭社区（<https://modelscope.cn>），再按下面任一方式发布。

### 方式 A：网页发布（推荐，评审可复现）

1. 生成待上传的 zip（脚本会校验魔搭社区的归档规则）：

   ```bash
   cd modelscope
   python pack_skill.py --out dist
   ```

   输出 `dist/financial-evidence-page-finder.zip`（约 24 KB）。
   校验点：归档根目录只有 1 个 `SKILL.md`；frontmatter 含 `name`/`description`/`version`；
   `name` 与目录名一致；体积小于 5 MB。

2. 打开技能中心 <https://www.modelscope.cn/skills>，登录后点击「发布技能 / 新建技能」。

3. 上传 `dist/financial-evidence-page-finder.zip`。

4. 填写表单（可直接照抄 `SKILL_UPLOAD_NOTES.md`）：

   | 字段 | 填写内容 |
   | --- | --- |
   | 名称 | 财报证据页检索 |
   | Skill 标识 | `financial-evidence-page-finder` |
   | 简介 | 见 `SKILL_UPLOAD_NOTES.md` |
   | 分类 | 文档处理（`doc-processing`） |
   | 许可证 | Apache License 2.0 |
   | 标签 | `pdf`、`财报`、`证据页检索`、`10-K`、`financial-report` |
   | 项目地址 | 本仓库 `modelscope/` 目录对应的 GitHub 地址 |

5. 发布。发布成功后 Skill 页面会给出可访问的链接与编号。

6. 打开 Skill 详情页，确认能看到 `SKILL.md` 内容（题面要求「确认能查看该 Skill 内容」），
   然后复制以下任意一项。

### 方式 B：命令行 / OpenAPI 发布（可复核的备选路径）

```bash
pip install modelscope
export MODELSCOPE_ENDPOINT="https://modelscope.cn"
export MODELSCOPE_API_KEY="<你的访问令牌>"     # 取令牌：https://modelscope.cn/my/myaccesstoken
```

步骤 1，上传 zip：

```bash
curl -X POST "$MODELSCOPE_ENDPOINT/openapi/v1/files/upload" \
  -H "Authorization: Bearer $MODELSCOPE_API_KEY" \
  -F "file=@dist/financial-evidence-page-finder.zip" -F "type=skill"
# 取返回的 data.id
```

步骤 2，创建 Skill：

```bash
curl -X POST "$MODELSCOPE_ENDPOINT/openapi/v1/skills" \
  -H "Authorization: Bearer $MODELSCOPE_API_KEY" -H "Content-Type: application/json" \
  -d '{"owner":"<你的用户名>","skill_name":"financial-evidence-page-finder",
       "display_name":"财报证据页检索","description":"<见 SKILL_UPLOAD_NOTES.md>",
       "skill_file":"<上一步的 data.id>","category":"doc-processing",
       "license":"Apache License 2.0",
       "tags":["pdf","财报","证据页检索","10-K","financial-report"],
       "source_url":"<本仓库地址>"}'
```

CLI 方式（`ms` 需要 `modelscope_hub`）：

```bash
ms create <你的用户名>/financial-evidence-page-finder --repo-type skill \
  --skill-file dist/financial-evidence-page-finder.zip
```

> 注意：`owner` 与 `skill_name` 创建后不可修改，发布前先确认用户名拼写。

### 发布后自查

```bash
curl "$MODELSCOPE_ENDPOINT/openapi/v1/skills/@<你的用户名>/financial-evidence-page-finder"
```

能看到 `display_name`、`description`、`category`、`install_command` 即发布成功。
也可以直接访问 <https://modelscope.cn/skills/<你的用户名>/financial-evidence-page-finder>。

## 七、提交给平台时该填什么

填 **Skill 自身的完整链接** 或 **完整编号**，二者任选其一：

| 交付物 | 填写内容（把 `<你的用户名>` 换成实际用户名） |
| --- | --- |
| Skill 网址（首选） | `https://modelscope.cn/skills/<你的用户名>/financial-evidence-page-finder` |
| Skill 编号 | `@<你的用户名>/financial-evidence-page-finder` |

**不要**填写个人主页、账号 ID、用户昵称，也不要只写 Skill 名称。
评测需要凭这一项定位到**这个 Skill 的页面**，填写下面的内容都会被判为无效提交：

- `https://modelscope.cn/profile/<你的用户名>`（个人主页）
- `<你的用户名>`（账号 ID）
- `财报证据页检索`（仅名称，无路径）

可以填完整 URL，也可以填 `owner/skill-name` 形式的完整编号；带不带 `@` 前缀都可以，
以链接形式最不容易出错。

## 八、与本仓库赛题四实现的关系

本 Skill 与本仓库赛题四「财报 PDF 全文解析与证据页检索」（PowerContext 赛题编号
`source-03-pdf-retrieval`）**同源**：它把赛题四的核心能力单独抽成一个可独立分发的 Agent Skill。

PowerContext 侧的对应实现位置（便于评审核对）：

| 文件 | 职责 |
| --- | --- |
| `src/powercontext/sources/pdf_pages.py` | 整份 PDF 逐页解析为页级 Source；文档 SHA-256；物理页码；页级引用回查 |
| `src/powercontext/sources/pdf_retrieval.py` | 离线词法证据打分：证据覆盖而非词频、报表分面、同义扩展、附注标题加权 |
| `competition/challenges/source-03-pdf-retrieval/` | 赛题四题面与公开自测集（503 页真实 10-K + 5 个公开问题） |

两者的关系与差异：

- **相同**：打分的核心思路一致——按问题证据的**覆盖度**排序，报表标题命中加权，
  金融概念做同义扩展，页码一律用物理页码并附文档摘要。
- **不同**：PowerContext 版跑在 Memory / Runtime 之上，页级 Source 会真实入库并返回可回查引用；
  本 Skill 是**独立实现**，不依赖 PowerContext 运行时、数据库或模型，只依赖 `pypdf`，
  因此装进任意 Agent 环境即可单独使用。打包脚本与脚本自检都在 `financial-evidence-page-finder/` 内。

本目录（`powercontext-ecosystem/modelscope/`）只存放本次「魔搭社区」赛题的可上传资产，
分支为 `2026-competition-ecosystem`。

## 九、许可

Skill 内容采用 Apache License 2.0。脚本与文档均为本仓库原创，不引用任何第三方模型或
受限语料；合成样例为虚构数据，不含真实公司信息。赛题四公开样例 PDF 属 FinanceBench
的 CC BY-NC 4.0 许可，仅按链接引用，未随包分发。

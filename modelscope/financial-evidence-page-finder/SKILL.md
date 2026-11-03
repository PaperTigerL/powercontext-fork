---
name: financial-evidence-page-finder
description: >-
  在处理 10-K、10-Q、年报、季报等财务报告 PDF 时使用。给定一份财报 PDF 与一个自然语言财务问题，
  逐页抽取文本并按问题词、短语与金融别名打分排序，返回可回查的证据页：物理页码、命中词、原文片段，
  并给出引用页列表。支持 income statement / balance sheet / cash flow 报表类型提示，
  以及 revenue 到 net sales、capex 到 purchases of property and equipment 一类的同义表述。
  当用户问“这条数据在财报的哪一页”“找出能回答这个问题的页码”“给出财报来源页与原文片段”
  “做财报证据页检索或引用回查”时使用；也适用于 .txt 与 .md 纯文本财报。
  不用于扫描件 OCR，不做最终数值计算或答案生成。
version: 1.0.0
license: Apache-2.0
---

# 财报证据页检索

给定一份财报 PDF 与一个财务问题，定位**可回查的证据页**：页码、命中的词、原文片段。

## 这个 Skill 解决什么问题

财报有几百页，答案通常只在一两页上。要引用一个数字，必须能说清“它来自第几页”。
本工具把整份 PDF 逐页抽成文本，按问题词、短语和金融领域别名给每页打分，返回得分最高的几页，
并摘出该页中承载证据的那几行，供人工核对。

## 何时使用

- 用户给出一份 10-K / 10-Q / 年报 PDF，问某个数字或某段说明在**哪一页**。
- 用户要求给出财报的**来源页码**与**原文片段**。
- 用户要在财报里做**证据页检索**：给定问题，列出最可能承载答案的页面。
- 财报已经是纯文本（`.txt` / `.md`），需要同样的页级定位。

## 何时不要用

- 扫描件（没有文本层）：本工具不包含 OCR，先做 OCR 再传入。
- 只要最终答案或数值：本工具**只定位证据页**，不做计算，也不生成结论。
- 跨大量文档的检索或需要向量/语义检索的场景：本工具是单文档的词法检索。

## 依赖

Python 3.9 及以上。除 PDF 输入外只需要一个第三方依赖：

```bash
pip install -r requirements.txt        # 仅需 pypdf
```

`--text` 模式（纯文本财报）不需要安装任何依赖。

## 快速开始

在**本 Skill 目录**下执行：

```bash
# 1) 生成一份极小的合成样例年报（无需任何依赖，可选）
python scripts/make_sample_pdf.py --out /tmp/sample_annual_report.pdf

# 2) 检索证据页
python scripts/find_evidence.py \
  --pdf /tmp/sample_annual_report.pdf \
  --question "What was the company's net sales in fiscal 2023?" \
  --topk 5
```

默认输出 Markdown 表格。也可以输出 JSON 便于程序消费：

```bash
python scripts/find_evidence.py --pdf report.pdf --question "capital expenditures" --format json
```

## 命令行参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--pdf PATH` | 二选一 | 财报 PDF 路径 |
| `--text PATH` | 二选一 | 纯文本财报路径，页之间用换页符 `\f` 分隔；不需要 pypdf |
| `--question TEXT` | 是 | 自然语言财务问题 |
| `--topk N` | 否 | 返回的证据页数量，默认 `5` |
| `--statement` | 否 | 报表类型提示：`auto`（默认，自动识别）、`income`（利润表）、`balance`（资产负债表）、`cashflow`（现金流量表） |
| `--format` | 否 | `markdown`（默认）、`json`、`text` |
| `--out PATH` | 否 | 把结果写入文件，而不是打印到标准输出 |
| `--min-score FLOAT` | 否 | 低于该得分的页面不返回，默认 `0` |
| `--max-snippet INT` | 否 | 片段最大字符数，默认 `320` |
| `--version` | 否 | 打印版本号 |

退出码：`0` 有命中；`1` 没有命中任何页面；`2` 输入错误（文件不存在、不是可读 PDF、参数冲突）。

## Agent 使用步骤

1. **确认输入**：拿到 PDF 路径（或纯文本路径）。若用户只给了文件名，先定位绝对路径。
2. **确认问题**：把用户的问题整理成一句完整的财务问题，保留指标名和年度，例如
   “What was net sales in fiscal 2023?”。问题里带上指标名比只带年度有效得多。
3. **运行检索**：
   ```bash
   python scripts/find_evidence.py --pdf <path> --question "<问题>" --topk 5
   ```
   若用户明确说了“利润表/资产负债表/现金流量表”，加上 `--statement income|balance|cashflow`。
4. **读取结果**：从表格里取 `物理页码`、`命中词`、`片段` 三列。
5. **回查核对**：用物理页码打开原 PDF 核对数字。**页码是 PDF 的物理页码（从 1 开始），
   不是财报印刷的页码**，两者常常不一致。同时用输出的 SHA-256 确认核对的是同一份文件。
6. **向用户交付**：给出页码 + 原文片段 + 文件摘要，并说明页码是物理页码。

## 输出说明

JSON 输出的主要字段：

| 字段 | 含义 |
| --- | --- |
| `document.path` / `document.sha256` | 输入文件路径与 SHA-256，用于确认回查的是同一份文件 |
| `document.page_count` | 解析到的物理页数 |
| `query.terms` / `query.phrases` / `query.aliases` | 从问题中抽出的检索词、短语与触发同义扩展的别名 |
| `query.statement_hints` | 识别到的报表类型 |
| `results[].page_number` | 物理页码，从 1 开始 |
| `results[].score` | 证据覆盖得分，越高越可能是答案所在页 |
| `results[].matched_terms` / `matched_phrases` / `matched_aliases` | 该页实际命中的词、短语、别名 |
| `results[].snippet` | 该页中承载证据的片段，命中处用 `[[ ]]` 标出 |
| `citation_pages` | 引用页列表，可直接写进结论 |

## 例子

### 例 1：问销售数字

```bash
python scripts/find_evidence.py --pdf report.pdf \
  --question "What was the company's net sales in fiscal 2023?" --topk 3
```

命中页通常就是 `CONSOLIDATED STATEMENTS OF OPERATIONS` 那一页，片段会摘出 `Net sales` 行。

### 例 2：问同义表述

```bash
python scripts/find_evidence.py --pdf report.pdf \
  --question "What were the company's capital expenditures in fiscal 2023?" --topk 3
```

财报一般不写 “capital expenditures” 这句话，而是写
`Purchases of property, plant and equipment`。本工具识别这类别名并把两种表述都命中，
因此现金流量表和对应的附注页都会进入候选。

### 例 3：指定报表类型

```bash
python scripts/find_evidence.py --pdf report.pdf \
  --question "How much total current assets did the company report?" \
  --statement balance --topk 3
```

`--statement balance` 让工具优先返回标题为资产负债表的页面。

### 例 4：纯文本财报

```bash
python scripts/find_evidence.py --text report.txt \
  --question "segment revenue" --topk 5 --format json
```

## 注意事项

- **页码口径**：输出的是 PDF 物理页码。10-K 目录里写的 “Consolidated Statements of Operations ..... 42”
  是印刷页码，与物理页码可能差几十页。回查时一律用物理页码。
- **扫描件**：没有文本层的 PDF 抽不出文字，工具会返回低分页面。此时需要先做 OCR。
- **表格布局**：pypdf 按文本流抽取，表格数字可能顺序错乱或与标题分离。片段用于定位，
  具体数值仍需打开原页核对。
- **同义词**：`revenue`、`sales`、`net sales`、`total revenues` 在不同公司含义不完全相同，
  工具按“同义扩展”处理，命中的是**页面**而不是结论，最终以原页为准。
- **多文档**：一次只处理一份文档。跨文档对比请分别运行并分别核对页码。

## 参考资料

- `references/scoring.md`：打分模型、权重与同义扩展表的说明。
- `references/reproduction.md`：用任意公开 10-K 复现的完整步骤。
- `examples/sample_questions.md`：可直接套用的示例问题与期望结果。

<!-- OB-S:YovEQtMAolusSewcpgeecA -->

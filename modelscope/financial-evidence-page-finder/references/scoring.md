# 打分模型说明

本文说明 `scripts/find_evidence.py` 如何给每一页打分。调参或排查误命中时读本文。

## 1. 为什么要按“证据覆盖”而不是词频打分

一个财报问题通常只由几个词决定答案页：指标名（`net sales`）、报表名（`income statement`）、
概念（`capital expenditures`）。哪一页的**标题**点名了这些词，哪一页就更可能是答案页。
反过来，一页里重复出现十次某个词，并不说明它是答案页。

所以打分是“覆盖”的函数，不是词频的函数。

## 2. 预处理

分词规则：文本转小写后，用正则 `[a-z]+|\d+` 切出词和数字。

每个词再归一化一次：

1. 长度大于 4 且以 `s` 结尾（不是 `ss`）时去掉 `s`：`sales` → `sale`，`expenditures` → `expenditure`；
2. 长度大于 5 时截断到前 5 个字符：`operating` → `opera`，`operations` → `opera`。

这是一个刻意粗糙的词干裁剪：它足以让财报里常见的同形词归一，同时避免引入
snowball / nltk 之类的额外依赖。数字不归一化。

每页会生成几个归一化视图：

| 视图 | 内容 | 用途 |
| --- | --- | --- |
| `normalized` | 整页 | 短语、别名是否出现 |
| `head_normalized` | 前 40 个词 | 短语是否出现在页首（标题区） |
| `wide_normalized` | 前 20 行 | 词是否出现在页面上部 |
| `top_normalized` | 前 6 行 | 页面标题是否点名某张报表 |
| `note_normalized` | 以 `Note N` 开头的行 | 词是否出现在附注标题里 |

## 3. 从问题里抽出检索单元

- **词**：去掉功能词后的实词，长度大于 1。
- **短语**：问题中长度 2 到 4 的连续词窗，要求首尾都是实词且窗内至少有两个实词。
  这样 “what is the fy” 不会变成可检索短语。
- **别名**：金融概念的不同说法，见第 6 节。
- **报表提示**：问题里出现 `income statement` / `balance sheet` / `cash flow` 等说法时，
  对应的报表标题会被加入检索单元。

## 4. 权重

| 证据 | 权重 | 说明 |
| --- | --- | --- |
| 实词命中 | `idf × 0.5` | 基础分。`idf` 按本文件内的词频计算，越少见越重要 |
| 实词出现在页面上部 | `idf × 1.0` | 追加 |
| 实词出现在附注标题 | `idf × 4.0` | 追加 |
| 短语命中 | `idf × 2.0` | 追加 |
| 短语出现在页首 | `idf × 4.0 + 6.0` | 追加 |
| 别名命中 | `idf × 2.0` | 追加 |
| 报表标题命中 | `20 × 命中数` | 每个被点名且标题命中的报表计一次 |
| 计算类问题且该页是报表页 | `+2.0` | 问题要的是从报表算出来的数（比率、百分比） |

页码顺序只在得分完全相同时用于打破平局，所以结果稳定可复现。

## 5. 报表识别

页面标题里出现下列说法之一，就认为该页是这张报表：

- 利润表：`consolidated statements of operations`、`consolidated statements of income` …
- 资产负债表：`consolidated balance sheets`、`consolidated statements of financial position` …
- 现金流量表：`consolidated statements of cash flows` …

另外，一页中数字占比达到 22% 也被视为报表页（表格密集）。

## 6. 同义扩展表

问题里出现左列的说法时，右列的说法也会被检索：

| 触发词 | 扩展为 | 关联报表 |
| --- | --- | --- |
| revenue | net sales, total revenues, net revenue | — |
| capital expenditure / capex | capital expenditures, additions to property, purchases of property, property plant and equipment | 现金流量表 |
| ebitda | operating income, operating profit, depreciation and amortization | 利润表、现金流量表 |
| gross margin | gross profit, cost of sales, cost of products | 利润表 |
| operating margin | operating income, operating profit, gross profit | 利润表 |
| effective tax rate | provision for income taxes, income tax expense | 利润表 |
| quick ratio / liquidity / working capital | current assets, current liabilities, cash and cash equivalents | 资产负债表 |
| days payable outstanding | accounts payable | 资产负债表 |
| segment | business segment, reportable segment, operating segment | — |
| geographies | north america, latin america, europe, asia pacific, middle east, africa | — |
| legal | legal proceedings, litigation, legal actions | — |
| customer concentration / primary customers | accounted for, customers, significant portion of our revenue … | — |

扩展表的作用是**找到页面**，不是给出结论。命中的别名会原样出现在输出的 `matched_aliases` 里，
便于判断是不是误命中。

## 7. 片段选取

输出片段取该页中“证据最集中”的几行，按下列顺序比较每一行：

1. 别名命中，每处记 3 分；
2. 短语命中，每处记 2 分；
3. 实词命中，每处记 1 分；
4. 单独一个年份最多记 3 分，只用于在前三项完全打平时做区分。

命中处在片段中用 `[[ ]]` 标出。

## 8. 已知局限

- 没有语义匹配：`revenue` 和 `sales` 能对上，但 `operating cash` 和 `funds from operations` 对不上。
- 表格抽取顺序不保证与视觉排版一致。
- 页面标题识别依赖英文报表名，中文或非英文报表不适用。
- 页码是物理页码，与财报印刷页码不一致。

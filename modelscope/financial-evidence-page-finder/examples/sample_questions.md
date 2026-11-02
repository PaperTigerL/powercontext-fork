# 示例问题与预期结果

下面的示例基于 `scripts/make_sample_pdf.py` 生成的合成年报（6 页，虚构公司）。
先运行：

```bash
python scripts/make_sample_pdf.py --out /tmp/sample_annual_report.pdf
```

样例页面构成：

| 物理页 | 内容 |
| --- | --- |
| 1 | 封面（FORM 10-K） |
| 2 | 目录 |
| 3 | `CONSOLIDATED STATEMENTS OF OPERATIONS`（含 `Net sales`、`Gross profit`、`Net income`） |
| 4 | `CONSOLIDATED BALANCE SHEETS`（含 `Cash and cash equivalents`、`Total current assets`） |
| 5 | `CONSOLIDATED STATEMENTS OF CASH FLOWS`（含 `Purchases of property, plant and equipment`） |
| 6 | `NOTE 8 - PROPERTY, PLANT AND EQUIPMENT`（含 `capital expenditures`） |

---

## 示例 1：直接指标

```bash
python scripts/find_evidence.py \
  --pdf /tmp/sample_annual_report.pdf \
  --question "What was the company's net sales in fiscal 2023?" --topk 3
```

预期：第 3 页排第一，命中词包含 `net sales`，片段摘出 `Net sales` 行。

## 示例 2：同义表述

```bash
python scripts/find_evidence.py \
  --pdf /tmp/sample_annual_report.pdf \
  --question "What were the company's capital expenditures in fiscal 2023?" --topk 3
```

预期：第 5 页与第 6 页排在前两名。`capital expenditures` 触发同义扩展
`purchases of property, plant and equipment`，因此现金流量表和附注 8 都会被命中。

## 示例 3：指定报表类型

```bash
python scripts/find_evidence.py \
  --pdf /tmp/sample_annual_report.pdf \
  --question "How much total current assets did the company report at the end of fiscal 2023?" \
  --statement balance --topk 3
```

预期：第 4 页排第一，得分远高于其余页面（`--statement balance` 会对标题为资产负债表的页面加权）。

## 示例 4：现金流量表指标

```bash
python scripts/find_evidence.py \
  --pdf /tmp/sample_annual_report.pdf \
  --question "What was net cash provided by operating activities in fiscal 2023?" \
  --statement cashflow --topk 3
```

预期：第 5 页排第一。

## 示例 5：资产负债表指标

```bash
python scripts/find_evidence.py \
  --pdf /tmp/sample_annual_report.pdf \
  --question "How much cash and cash equivalents did the company hold at the end of fiscal 2023?" \
  --topk 3
```

预期：第 4 页排第一。

## 示例 6：JSON 输出

```bash
python scripts/find_evidence.py \
  --pdf /tmp/sample_annual_report.pdf \
  --question "capital expenditures" --topk 1 --format json
```

输出结构：

```json
{
  "tool": "find_evidence",
  "version": "1.0.0",
  "question": "capital expenditures",
  "query": {
    "terms": ["capital", "expenditures"],
    "phrases": ["capital expenditures"],
    "aliases": ["capital expenditures", "additions to property", "purchases of property", "property plant and equipment"],
    "statement_hints": ["cashflow"],
    "computational_intent": true
  },
  "results": [
    {
      "rank": 1,
      "page_number": 5,
      "score": 46.3554,
      "is_statement_page": true,
      "statement_facets": ["cashflow"],
      "matched_terms": [],
      "matched_phrases": [],
      "matched_aliases": ["property plant and equipment", "purchases of property"],
      "snippet": "[[Purchases of property]], plant and equipment            (640)     (520) ..."
    }
  ],
  "citation_pages": [5],
  "document": {
    "path": "/tmp/sample_annual_report.pdf",
    "sha256": "433a8bff8caa67d548b6b76109c9ee02955d4092841aa192e49c98491cb8525b",
    "page_count": 6,
    "source": "pdf"
  }
}
```

`matched_aliases` 直接说明了这一页**为什么**被选中，便于判断是不是误命中。

---

## 真实财报上的表现

在赛题四公开样例（503 页 10-K）上实测：

| 问题 | 命中的关键页 | 说明 |
| --- | --- | --- |
| 主营地区有哪些 | 第 5 页（Item 1 Business 的地区列表） | `geographies` 别名展开成各大区名称 |
| FY2022 EBITDA 减 capex | 第 64 页（现金流量表）、第 54 页（MD&A `Capital spending`） | 计算类问题触发 `ebitda`、`capex` 别名 |
| 有无重大未决诉讼 | 第 25、24 页（法律风险因素正文） | `legal` 别名展开成 `legal proceedings`；第 4 页是 `Litigation Reform Act` 的误命中 |
| 利润表中列示的重组费用 | 第 105 页（重组附注）、第 62 页（`Consolidated Statement of Income`） | 报表名与附注标题直接命中 |

最后两行说明词法检索会有误命中，因此工具把命中词原样输出（`matched_terms` /
`matched_aliases`），便于判断某页是**因为哪个词**被选中的。

详见 `references/reproduction.md`。

# 复现步骤

本文给出三种复现方式，从最轻到最真实。

## 方式 A：内置合成样例（零依赖，最快）

样例是一份虚构公司的极小年报，不含任何真实公司数据。生成脚本只依赖 Python 标准库。

```bash
# 1. 生成样例 PDF（6 页）
python scripts/make_sample_pdf.py --out /tmp/sample_annual_report.pdf

# 2. 检索证据页
python scripts/find_evidence.py \
  --pdf /tmp/sample_annual_report.pdf \
  --question "What was the company's net sales in fiscal 2023?" \
  --topk 5
```

样例包含 6 页：封面、目录、利润表、资产负债表、现金流量表、以及 `NOTE 8 - PROPERTY, PLANT AND EQUIPMENT`。
预期结果：利润表页（第 3 页）排在第一。

```bash
# 同义表述：capex 在财报里写作 "purchases of property, plant and equipment"
python scripts/find_evidence.py \
  --pdf /tmp/sample_annual_report.pdf \
  --question "What were the company's capital expenditures in fiscal 2023?" --topk 3
```

预期结果：第 5 页（现金流量表）与第 6 页（附注 8）排在前面。

```bash
# 指定报表类型
python scripts/find_evidence.py \
  --pdf /tmp/sample_annual_report.pdf \
  --question "How much total current assets did the company report?" \
  --statement balance --topk 3
```

预期结果：第 4 页（资产负债表）排在第一。

## 方式 B：任意公开 10-K（推荐）

1. 到 SEC EDGAR 检索目标公司的年报：
   <https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=10-K>
2. 打开某一期 filing，取 `Document Format Files` 里的主文档（通常是第一个 `.htm` 或 `.txt`，
   或 `EX-10` 之类的 PDF 附件）。
3. 存成 `.pdf`（若拿到的是 `.htm`，先用浏览器的“打印为 PDF”导出，务必保留页序）。
4. 运行检索：

```bash
python scripts/find_evidence.py \
  --pdf /path/to/company_10k.pdf \
  --question "What was net revenue for fiscal 2023?" --topk 5
```

5. 用输出的物理页码打开 PDF 核对。注意 SEC 的 HTML 转 PDF 与官方 PDF 的分页不同，
   核对时以本次使用的那个 PDF 为准。

## 方式 C：上游赛题的公开样例（本仓库同源能力所用）

PowerContext 赛题四（`source-03-pdf-retrieval`）的公开自测集里有一份完整的 10-K PDF 和 5 个原始问题：

- 样例目录：<https://github.com/patronus-ai/financebench/tree/cc39aeb4afdf33909ee1412188bf89035950c2eb>
- 原始 10-K：<https://raw.githubusercontent.com/patronus-ai/financebench/cc39aeb4afdf33909ee1412188bf89035950c2eb/pdfs/PEPSICO_2022_10K.pdf>
- 许可：CC BY-NC 4.0（FinanceBench 数据卡）。该文件**不随本 Skill 分发**，请按许可自行下载使用。

该 PDF 共 503 个物理页，登记的 SHA-256 为
`7d8a9f3374e429c58f101319e2da8a0e601a89859e1e4f6854163dd5f8ce6b47`。

下载后先确认工具算出的摘要一致：

```bash
python scripts/find_evidence.py \
  --pdf PEPSICO_2022_10K.pdf \
  --question "What are the geographies that Pepsico primarily operates in as of FY2022?" \
  --topk 5 --format text
```

预期：`document.sha256` 与上面登记的值一致；命中的第一页是 Item 1 Business 中列举
Latin America / Europe / Africa, Middle East and South Asia / Asia Pacific 的那一页。

再跑一个需要跨两张报表取数的问题：

```bash
python scripts/find_evidence.py \
  --pdf PEPSICO_2022_10K.pdf \
  --question "What is the FY2022 unadjusted EBITDA less capex for PepsiCo? Define unadjusted EBITDA as unadjusted operating income + depreciation and amortization from the cash flow statement." \
  --topk 5 --format text
```

预期：靠前的两页分别是 `Consolidated Statement of Cash Flows`（含 `Depreciation and amortization`）
和 MD&A 中的 `Capital spending` 一页。

## 纯文本输入

财报已经抽成文本时，页之间用换页符 `\f`（U+000C）分隔即可，不需要 pypdf：

```bash
python scripts/find_evidence.py --text report.txt --question "segment revenue" --topk 5
```

## 批量运行

```bash
for q in "net sales" "total current assets" "capital expenditures"; do
  python scripts/find_evidence.py --pdf report.pdf --question "$q" --topk 3 --format json \
    --out "result_$(echo "$q" | tr ' ' '_').json"
done
```

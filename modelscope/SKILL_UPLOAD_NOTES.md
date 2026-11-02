# 发布到魔搭社区：可粘贴字段清单

按顺序做完这 4 步，大约 3 分钟。详细背景见同目录 `README.md`。

## 第 1 步：打包

```bash
cd modelscope
python pack_skill.py --out dist
```

期望输出：

```
前置校验通过: financial-evidence-page-finder
已生成 dist/financial-evidence-page-finder.zip（约 24 KB，7 个文件）
```

得到 `dist/financial-evidence-page-finder.zip`。

## 第 2 步：发布表单字段

进入 <https://www.modelscope.cn/skills>，登录后「发布技能 / 新建技能」，上传上一步的 zip。

| 字段 | 直接粘贴 |
| --- | --- |
| 名称（display_name） | `财报证据页检索` |
| Skill 标识（skill_name） | `financial-evidence-page-finder` |
| 分类（category） | `doc-processing`（文档处理） |
| 许可证（license） | `Apache License 2.0` |
| 标签（tags） | `pdf`、`财报`、`证据页检索`、`10-K`、`financial-report` |
| 项目地址（source_url） | 本仓库 `modelscope/` 目录的 GitHub 完整地址（分支 `2026-competition-ecosystem`） |

> `owner`（你的魔搭用户名）与 `skill_name` **创建后不可修改**，发布前先核对用户名拼写。

### 简介（description）

中文版（推荐直接用这段）：

```
在处理 10-K、10-Q、年报、季报等财务报告 PDF 时使用。给定一份财报 PDF 与一个自然语言财务问题，
逐页抽取全文并按问题词、短语与金融同义表述打分排序，返回可回查的证据页：物理页码、命中词、
原文片段，并给出引用页列表。支持 income statement / balance sheet / cash flow 报表类型提示，
以及 revenue 到 net sales、capex 到 purchases of property and equipment 一类的同义表述。
当用户问「这条数据在财报的哪一页」「找出能回答这个问题的页码」「给出财报来源页与原文片段」
「做财报证据页检索或引用回查」时使用；也适用于 .txt 与 .md 纯文本财报。
不用于扫描件 OCR，不做最终数值计算或答案生成。
```

英文版（若平台要求填英文简介，或想同时覆盖英文检索）：

```
Use when working with 10-K, 10-Q, annual or quarterly report PDFs. Given a financial report PDF and
one natural-language question, this skill parses every physical page, scores pages by evidence
coverage (question terms, phrases and finance-domain aliases), and returns citable evidence pages:
physical page number, matched words, an excerpt, and a citation page list. Supports income statement /
balance sheet / cash flow statement hints and synonym expansion such as revenue -> net sales and
capex -> purchases of property, plant and equipment. Trigger it when the user asks which page of a
report answers a question, needs a source page number with the original wording, or wants evidence
page retrieval over a financial report. Not for scanned OCR, final calculations or answer generation.
```

## 第 3 步：发布后自查

打开 Skill 详情页，确认能看到 `SKILL.md` 的正文内容（题面要求「确认能查看该 Skill 内容」）。

命令行核对：

```bash
curl "https://modelscope.cn/openapi/v1/skills/@<你的用户名>/financial-evidence-page-finder"
```

能看到 `display_name`、`description`、`category`、`install_command` 即发布成功。

## 第 4 步：提交给平台

填 **Skill 自身的完整链接** 或 **完整编号**，二者任选其一：

| 交付物 | 填写内容 |
| --- | --- |
| Skill 网址（首选） | `https://modelscope.cn/skills/<你的用户名>/financial-evidence-page-finder` |
| Skill 编号 | `@<你的用户名>/financial-evidence-page-finder` |

不要填个人主页、账号 ID、用户昵称，也不要只填 Skill 名称——评测要凭这一项定位到
**这个 Skill 的页面**。下面这些都会被判为无效提交：

- `https://modelscope.cn/profile/<你的用户名>`
- `<你的用户名>`
- `财报证据页检索`

## 附：示例输入输出（可放进 README 或演示）

输入：

```
python scripts/find_evidence.py --pdf report.pdf \
  --question "What was the company's net sales in fiscal 2023?" --topk 5
```

输出（Markdown 表格，节选）：

```
| 排名 | 物理页码 | 得分 | 命中词 | 片段 |
| --- | --- | --- | --- | --- |
| 1 | 3 | 16.4129 | 2023, net, sales, net sales | [[Net sales]]  12,480  11,020  9,745 ... |
```

输出（JSON，节选）：

```json
{
  "document": { "sha256": "7d8a9f33...", "page_count": 503 },
  "results": [
    { "rank": 1, "page_number": 64, "score": 223.2688,
      "matched_aliases": ["purchases of property", "property plant and equipment"],
      "snippet": "[[Purchases of property]], plant and equipment ..." }
  ],
  "citation_pages": [64]
}
```

## 附：万一网页表单不可用

用 OpenAPI 发布，效果与网页一致：

```bash
export MODELSCOPE_ENDPOINT="https://modelscope.cn"
export MODELSCOPE_API_KEY="<令牌：https://modelscope.cn/my/myaccesstoken>"

curl -X POST "$MODELSCOPE_ENDPOINT/openapi/v1/files/upload" \
  -H "Authorization: Bearer $MODELSCOPE_API_KEY" \
  -F "file=@dist/financial-evidence-page-finder.zip" -F "type=skill"
# 取返回的 data.id，再 POST /openapi/v1/skills，owner / skill_name / display_name /
# description / skill_file / category / license / tags / source_url
```

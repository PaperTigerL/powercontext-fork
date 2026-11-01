# SPEC-BILL-001 计费记录筛选（v1）

> 规格版本：v1
> 适用工程：`sample_project`（billing）

## 需求

为计费记录列表提供过滤能力，并保持过滤前后的可预测行为。

## 约束条目

| 条目 ID | 约束 |
| --- | --- |
| SPEC-BILL-001-A | 必须支持按最小金额 `min_amount` 过滤，仅保留 `amount >= min_amount` 的记录。 |
| SPEC-BILL-001-B | 必须支持按币种 `currency` 过滤，仅保留 `currency` 完全相等的记录。 |
| SPEC-BILL-001-C | 过滤必须保持输入记录的原始顺序。 |
| SPEC-BILL-001-D | 输入为空列表时返回空列表，且不得抛出异常。 |
| SPEC-BILL-001-E | 未提供的过滤条件不得生效（不得使用默认值改变结果）。 |

## 不在本版本范围内

- 按状态过滤（见 `billing_filter_v2.md`）。
- 分页、排序、聚合。

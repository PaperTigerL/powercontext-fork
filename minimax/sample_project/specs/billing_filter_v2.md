# SPEC-BILL-001 计费记录筛选（v2）

> 规格版本：v2（替代 v1）
> 适用工程：`sample_project`（billing）
> 变更摘要：在 v1 基础上新增按状态过滤，并明确多条件交集语义。

## 约束条目

| 条目 ID | 约束 | 变更 |
| --- | --- | --- |
| SPEC-BILL-001-A | 必须支持按最小金额 `min_amount` 过滤，仅保留 `amount >= min_amount` 的记录。 | 沿用 v1 |
| SPEC-BILL-001-B | 必须支持按币种 `currency` 过滤，仅保留 `currency` 完全相等的记录。 | 沿用 v1 |
| SPEC-BILL-001-C | 过滤必须保持输入记录的原始顺序。 | 沿用 v1 |
| SPEC-BILL-001-D | 输入为空列表时返回空列表，且不得抛出异常。 | 沿用 v1 |
| SPEC-BILL-001-E | 未提供的过滤条件不得生效（不得使用默认值改变结果）。 | 沿用 v1 |
| SPEC-BILL-001-F | 必须支持按状态 `status` 过滤，仅保留 `status` 完全相等的记录；未提供 `status` 时不得按状态过滤。 | **新增** |
| SPEC-BILL-001-G | 同时给出多个过滤条件时，结果为各条件结果的交集。 | **新增** |
| SPEC-BILL-001-H | `status` 不得成为位置参数，必须为仅关键字参数。 | **新增** |

## 验收对应

- 目标功能测试：`sample_project/tests/test_target.py`
- 回归测试：`sample_project/tests/test_regression.py`（覆盖 v1 的 A–E）

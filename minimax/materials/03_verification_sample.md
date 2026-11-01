# 材料 3 · 验证样例

> 完整说明见 `../README.md` 第 3 节；本文件给出评审可直接复核的**具体文件与命令**。

## 1. 样例资产

| 资产 | 路径 |
| --- | --- |
| 任务描述 | 本文件第 2 节 + `../scripts/record_session.py` 的 `TASK` 常量 |
| 规格 v1（旧） | `../sample_project/specs/billing_filter_v1.md` |
| 规格 v2（当前） | `../sample_project/specs/billing_filter_v2.md` |
| 初始数据 | `../sample_project/src/billing/records.py` 的 `SAMPLE` |
| 修改前代码快照 | `../sample_project/src/billing/filter.py` |
| 修改后代码快照 | `../transcript/after/src/billing/filter.py` |
| 目标功能测试 | `../sample_project/tests/test_target.py` |
| 回归测试 | `../sample_project/tests/test_regression.py` |

## 2. 任务描述

> 实现规格 `SPEC-BILL-001-F` 要求的按状态过滤：
> `filter_records(records, *, status="paid")` 只保留 `status` 完全相等的记录；
> `status` 为仅关键字参数；多个过滤条件取交集；保持输入顺序。

## 3. 操作步骤（评审可逐条复核）

```bash
cd minimax
export PYTHONPATH="$PRODUCT/src:$PWD"

# 步骤 1：初始化数据（规格 v1）
python -m ctxmodule import --project sample_project \
    --spec sample_project/specs/billing_filter_v1.md

# 步骤 2：执行样例（规格 v1）——此时上下文中不含 SPEC-BILL-001-F
python -m ctxmodule context --task-id TASK-BILL-001 --task "..." \
    --require-spec SPEC-BILL-001-F

# 步骤 3：更新规格并重新导入（规格 v2）
python -m ctxmodule import --project sample_project \
    --spec sample_project/specs/billing_filter_v2.md

# 步骤 4：再次执行样例——此时上下文含 SPEC-BILL-001-F/G/H
python -m ctxmodule context --task-id TASK-BILL-001 --task "..." \
    --require-spec SPEC-BILL-001-F --require-spec SPEC-BILL-001-G \
    --require-spec SPEC-BILL-001-H

# 步骤 5：修改前跑目标测试（必须失败，且失败原因是行为缺失）
cd sample_project && PYTHONPATH=src python -m pytest -q tests/test_target.py

# 步骤 6：应用 MiniMax 产出的补丁
git apply -p1 ../transcript/feature.patch

# 步骤 7：再次跑目标测试与回归测试（必须全部通过）
PYTHONPATH=src python -m pytest -q tests/test_target.py tests/test_regression.py
```

## 4. 预期结果

| 步骤 | 预期 |
| --- | --- |
| 1 | `document_count` ≥ 4；`kind` 覆盖 `spec` / `code` / `test` |
| 2 | `spec.items` 只有 SPEC-BILL-001-A；`sources` 含 `spec:billing_filter_v1.md` |
| 3 | `spec:active` 行内容被替换；`document_count` 不变 |
| 4 | `spec.items` 含 SPEC-BILL-001-F/G/H；`spec.source_hash` 与步骤 2 不同 |
| 5 | 退出码非 0；输出含 `TypeError: filter_records() got an unexpected keyword argument 'status'`；**不是** collection error |
| 6 | `git apply` 退出码 0 |
| 7 | 退出码 0，全部 passed |

## 5. 重置方法

```bash
# 回到修改前状态
cd minimax/sample_project
git checkout -- .            # 若该目录是 git 跟踪的；否则重新克隆样本工程
rm -rf ../.ctxmodule-data    # 清空本地 seekdb 与 PowerContext 数据
```

`../sample_project/src/billing/filter.py` 在仓库中保存的就是修改前快照，
重新获取本目录即可回到初始状态。规格可通过选择 `--spec` 在 v1 / v2 之间切换，
无需改动任何代码。

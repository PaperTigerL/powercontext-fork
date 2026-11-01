# 样例业务工程（sample_project）

这是本次任务的被修改对象：一个最小但**可运行、有测试**的 Python 业务工程。

```
sample_project/
├── specs/
│   ├── billing_filter_v1.md      规格 v1（约束 A–E）
│   └── billing_filter_v2.md      规格 v2（约束 A–H，新增 status 过滤）
├── src/billing/
│   ├── __init__.py
│   ├── filter.py                 被修改的文件（仓库中保存的是**修改前**快照）
│   └── records.py                记录类型与固定数据（回归保护对象）
└── tests/
    ├── test_target.py            目标功能测试（SPEC-BILL-001-F/G/H）
    └── test_regression.py        回归测试（SPEC-BILL-001-A..E）
```

## 运行

```bash
PYTHONPATH=src python -m pytest -q tests/test_target.py tests/test_regression.py
```

## 当前状态

`src/billing/filter.py` 只实现了 v1 规格，**没有** `status` 关键字参数，
因此 `tests/test_target.py` 在当前快照下失败，失败原因为：

```
TypeError: filter_records() got an unexpected keyword argument 'status'
```

这是「修改前因目标行为未实现而失败」的预期起点。
本次任务产出的补丁见 `../transcript/feature.patch`，应用后目标测试与回归测试全部通过。

> 说明：题目允许复用任意「能够运行、具有测试的业务工程」。
> 本目录提供这个最小工程是为了让验收在干净环境中可复现；
> 若改用你自己的工程，把目录整体替换即可，规格条目与测试需同步更新。

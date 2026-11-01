# 材料 4 · 代码与测试

## 1. 修改前后代码快照

| 版本 | 路径 | 说明 |
| --- | --- | --- |
| 修改前 | `../sample_project/src/billing/filter.py` | 仓库中保存的就是修改前快照，只实现了 v1 规格（A–E），`status` 关键字尚未实现 |
| 修改后 | `../transcript/after/src/billing/filter.py` | 本次任务产出的修改后快照，实现了 v2 规格（A–H） |

两个快照的唯一差别就是本次任务要求的变更，因此评审可以直接对比。

## 2. 代码差异

统一 diff 保存在 `../transcript/feature.patch`：

```bash
cd minimax/sample_project
git apply -p1 ../transcript/feature.patch
```

该补丁由 MiniMax 在录制的开发会话中产出（见材料 5），
其 sha256 与 `../transcript/minimax_session.jsonl` 中记录的 `diff_sha256` 一致，
门禁 2 会校验这一点。

## 3. 测试

| 类别 | 文件 | 覆盖的规格条目 |
| --- | --- | --- |
| 目标功能测试 | `../sample_project/tests/test_target.py` | SPEC-BILL-001-F / G / H（本次新增行为） |
| 回归测试 | `../sample_project/tests/test_regression.py` | SPEC-BILL-001-A / B / C / D / E（改动前既有行为） |

运行方式：

```bash
cd minimax/sample_project
PYTHONPATH=src python -m pytest -q tests/test_target.py tests/test_regression.py
```

## 4. 测试日志

自测运行时，门禁 6 会把三份日志写到 `../artifacts/`：

| 文件 | 内容 |
| --- | --- |
| `artifacts/target-tests-before.log` | 修改前的目标功能测试结果（**必须失败**，且失败原因是 `TypeError: filter_records() got an unexpected keyword argument 'status'`，即目标行为未实现） |
| `artifacts/target-tests-after.log` | 应用补丁后的目标功能测试结果（必须全部通过） |
| `artifacts/regression-tests-after.log` | 修改后的回归测试结果（必须全部通过） |

每份日志都是 JSON，包含：

| 字段 | 含义 |
| --- | --- |
| `command` | 实际执行的命令 |
| `exit_code` | 退出码 |
| `stdout` / `stderr` | 测试输出 |
| `passed` | 是否通过 |
| `code_version` | 日志对应的代码版本（`git rev-parse HEAD`） |

> 日志目录默认是 `minimax/artifacts/`。它记录的是运行产物，不随源码提交；
> 需要作为材料提交时，请把三份日志复制到本目录并附上对应的 commit。

## 5. 关于「修改前失败」的说明

门禁 6 额外断言了修改前的失败**不是**下列环境类原因：

- `error collecting` / `ModuleNotFoundError` / `ImportError while importing test module`
- 缺少依赖、服务不可达等

即失败必须来自生产代码本身缺少目标行为，而不是测试跑不起来。

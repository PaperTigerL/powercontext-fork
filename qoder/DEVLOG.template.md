# Qoder 开发记录 · MemCoach

> 模板文件。参赛者按 `qoder/PROMPT.md` 的五个阶段推进，每阶段结束后把 Qoder 输出的
> 「本阶段小结」和关键片段整理进对应小节。**评审会按这份文件核对开发过程。**

- 项目：MemCoach · 记忆复习教练
- 仓库：`<填仓库 URL>`
- 分支：`2026-competition-ecosystem`
- 参赛者：`<填姓名/账号>`
- 记录起始日期：`<YYYY-MM-DD>`

---

## 阶段 1 · 需求拆解与架构设计

**Qoder 做了什么：**

```
（粘贴 Qoder 的「本阶段小结」）
```

**产出物：**

- [ ] 功能清单（含已实现 / 待补齐 / 优先级）
- [ ] 数据流说明（remember → search → 复用 → 用户可见）
- [ ] 技术选型说明
- [ ] 风险清单

**读了哪些参考文件：**

- `openapi/powercontext.yaml`
- `docs/zh/docs/develop/http-api.md`
- `dify/scripts/verify_memory_api.py`
- `dify/dsl/night-store-npc.yml`

**本阶段验证命令与结果：**

```
（粘贴命令与输出）
```

---

## 阶段 2 · 数据模型与 PowerContext 接口设计

**Qoder 做了什么：**

```
（粘贴 Qoder 的「本阶段小结」）
```

**产出物：**

- [ ] 记忆条目正文格式（最终版）
- [ ] MemoryStore 接口契约（list / remember / search）
- [ ] PowerContext 错误码映射表
- [ ] scope 语义说明

**改动的文件：**

| 文件 | 改了什么 |
| --- | --- |
|  |  |

**本阶段验证命令与结果：**

```
（粘贴命令与输出）
```

---

## 阶段 3 · 编码

**Qoder 做了什么：**

```
（粘贴 Qoder 的「本阶段小结」）
```

**产出物：**

- [ ] 记忆复用效果在页面上可见
- [ ] 掌握度影响复习排序
- [ ] 记忆库显示 citation / version / state
- [ ] 输入校验与错误提示
- [ ] 无 TODO / 空壳

**改动的文件：**

| 文件 | 改了什么 |
| --- | --- |
|  |  |

**本阶段验证命令与结果：**

```
（粘贴命令与输出）
```

---

## 阶段 4 · 调试与自测

**Qoder 做了什么：**

```
（粘贴 Qoder 的「本阶段小结」）
```

**逐条自测结果（对应 `qoder/VERIFICATION.md`）：**

| 样例 | 结果 | 实际输出摘要 |
| --- | --- | --- |
| V1 未登录打开网站 | ☐ 待补测 | |
| V2 演示模式开箱可交互 | ☐ | |
| V3 实时写入 PowerContext | ☐ | |
| V4 检索复用可见 | ☐ | |
| V5 掌握度闭环 | ☐ | |
| V6 故障清晰报错 | ☐ | |
| V7 按说明跑通 | ☐ | |
| V8 开发记录完整 | ☐ 待补测 | |

**实测过的故障场景与真实报错：**

```
（粘贴 1）未配置 POWERCONTEXT_URL / POWERCONTEXT_SCOPE_ID 且 MEMCOACH_MODE=live
（粘贴 2）配置了地址但服务连不上
```

**「PowerContext 不可用会怎样」说明：**

```
（粘贴说明）
```

---

## 阶段 5 · 部署与 Qoder Sites 发布

**Qoder 做了什么：**

```
（粘贴 Qoder 的「本阶段小结」）
```

**发布配置：**

| 项 | 值 |
| --- | --- |
| 发布根目录 | `qoder/app/public` |
| 可见范围 | 任何人都可访问（**必须用个人账号**，企业版无法设置公开访问） |
| Qoder Sites 网址 | `<待填>` |
| 后端部署地址（实时模式） | `<待填，或说明本次以演示模式交付>` |

**发布后验证：**

```
（粘贴 V1 / V7 的实际结果）
```

**发布产物安全检查：**

```
grep -rn "Bearer\|POWERCONTEXT_TOKEN=" qoder/app/public || echo "public 下没有 token 痕迹"
```

---

## 附：Qoder 会话记录存放位置

- Qoder 客户端内的会话历史：`<填写会话名称或导出文件位置>`
- 本文件：仓库路径 `qoder/DEVLOG.md`

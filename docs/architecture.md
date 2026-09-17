# 架构与目录（第一批实现视角）

定稿方案见 `../架构评审/LivingMind-架构评审与迁移步骤-v0.2.md`。本文件只记录**代码里实际怎么分**，以及哪些位置是后续预留。

## 请求链路（步骤 4 起）

```text
App 页面 → services/api（http 实现）→ FastAPI 路由
  → 校验演示身份（account / person / space）
  → 规划 services/planner.py：规则 rules/rest_rule.py，或 Experience Agent agents/experience/（不改设备）
      模型失败（未配置 / 超时 / 网络 / HTTP / 非法 JSON / 不符结构）→ 规则降级，附原因
  → 用户确认 → 执行器 harness/executor.py（白名单、参数范围、服务是否仍有效）
  → 虚拟设备 adapters/virtual/devices.py（真实维护状态）
  → 回读设备状态 → 写活动记录 → 返回 App

模拟事件（⑥）：POST /api/spaces/{spaceId}/events（source=simulated）
  → 锁内检查：有活跃服务？上一次调整还在进行？次数上限？冷却时间？
  → 锁外规划：Planner.plan_adjustment（跟随服务的规则/模型模式；同样有降级与偏离上限）
  → 锁内复查服务仍 active 且代次未变 → 只对有变化的设备生成动作
  → 执行器（同一 guard）→ 回读 → 活动记录（event_received / event_ignored / service_adjusted）
```

## 模块职责

| 位置 | 职责 | 状态 |
|---|---|---|
| `apps/mobile/features/` | 按业务划分的页面内容：home（人物）、rest（需求/计划/确认/停止）、devices、activity | 第一批实现 |
| `apps/mobile/components/`、`theme/` | 基础组件与设计 token（颜色取自演示设计规范） | 第一批实现 |
| `apps/mobile/services/` | `api.ts` 接口定义；`http/` 真实 API；`mock/` 前端模拟 | 第一批实现 |
| `backend/app/contracts/` | Pydantic 数据契约，是前端类型的唯一来源 | 第一批实现 |
| `backend/app/api/` | HTTP 路由与统一错误格式 | 第一批实现 |
| `backend/app/rules/` | 固定休息规则 + 规则/模型共用的动作映射 | 第一批实现 |
| `backend/app/services/planner.py` | 规则/模型切换与降级 | ⑤ 实现 |
| `backend/app/agents/experience/` | Experience Agent：提示词、输出结构校验、DeepSeek Provider | ⑤ 实现 |
| `backend/app/harness/` | 统一执行器与检查规则 | 第一批最小版 |
| `backend/app/services/` | 服务生命周期（active / stopped）、确认幂等、停止失效 | 第一批实现 |
| `backend/app/adapters/virtual/` | 有状态虚拟灯光、空调、窗帘 | 第一批实现 |
| `backend/app/repositories/` | 内存存储（重启重置） | 第一批实现 |
| `backend/app/demo/` | 种子人物、空间、演示账户 | 第一批实现 |
| `packages/api-client/` | 由 OpenAPI 生成的 TS 类型 | 第一批实现 |
| `backend/app/agents/orchestrator/`、`space_execution/` | 主 Agent / 执行 Agent | **未创建**，第二批 ⑧ |
| `backend/app/memory/`、`energy/` | 人物记忆、能源规则 | **未创建**，第二批 ⑧ |
| 事件入口与调整（`services/rest_service.py::inject_event`、`rules/rest_rule.py::adjustment_rule`） | 一次事件调整 | ⑥ 实现 |
| 定时器、SpaceMind / 语音 Adapter | 整晚服务与真实接入 | **未创建**，⑦ 及以后 |

按“只建当前需要的模块”原则，未实现的模块不建空目录。

## 身份说明

- 当前只有**演示身份**：固定演示账户 `demo-account`，其成员关系在 `backend/app/demo/seed.py`。
- App 里的“选择人物”只是切换上下文；后端会检查该人物、空间是否属于演示账户，但这**不是登录授权**。
- 正式认证属于后续批次；在此之前后端不得部署到公网。

## 关键规则（后端强制，不只靠界面按钮）

1. 创建计划不改变设备。
2. 同一计划重复确认不会重复执行（按计划状态幂等返回）。
3. 同一空间同时只允许一个活跃休息服务。
4. 停止会让该空间此前生成的计划全部失效（空间“代次” epoch +1）；执行器在**每个动作前**、在服务锁内重查服务仍为 active 且代次一致。
5. 设备写入在服务锁**之外**执行，所以慢设备不会挡住停止请求；已开始的那个动作会完成，之后的动作被跳过（`tests/test_concurrency.py`）。
6. 停止保持设备当前状态，不自动恢复。
7. 计划 10 分钟后过期。
8. 所有设备写入经过执行器：工具白名单 + 参数范围。
9. 数据存在内存里，后端重启即重置；`POST /api/demo/reset` 可手动重置（会写一条 `demo_reset` 记录）。
10. 计划一经确认即标为 `executed`，表示“已被采纳”；每个动作的真实结果以 `results` 为准。执行过程中重复确认，返回的是当时已完成的部分。
11. 同一演示账户下的任何人物都能停止空间里正在运行的服务，不要求是发起人。这是有意的：共享空间里，谁都应该能让设备停下来。
12. 模型计划相对本人偏好的偏离有上限：灯光与窗帘 ±40、空调 ±3°C（`services/planner.py` 的 `MAX_DEVIATION`）；超出即改用规则计划并标注原因。这是“体验是约束”在代码里的落点，由后端强制，不只靠提示词。
13. 未预期的异常统一返回 `INTERNAL_ERROR`（500），不暴露堆栈；详细信息只写服务器日志。
14. App 等待计划的时间 = 后端模型超时 + 3 秒（从 bootstrap 读取），避免 App 先于后端放弃；事件请求同样；其他请求仍是 8 秒。
15. 事件只调整正在运行的服务：没有服务、上一次调整未结束、达到次数上限（默认 3）、冷却中（默认 30 秒）都会忽略并记录原因。每个服务同时只有一个调整在进行。
16. 事件的规则调整：室温偏离空调设定 2°C 以上时，空调每次调 1°C，且不超出本人偏好 ±3°C；灯光和窗帘不动。模型调整只执行与当前状态不同的项，仍受偏离上限约束。
17. 事件调整跟随服务的计划模式（`Service.plannerMode`）：规则模式启动的服务，事件时也不调用模型。
18. 调整次数在执行前计数；执行中被停止，剩余动作跳过，已开始的那一个不撤销。

## 模型调用边界（⑤）

- 模型只生成体验目标和三个数值；输出先过 Pydantic 结构与范围校验，再变成普通 `Plan`，确认后走同一个执行器。模型不能直接写设备。
- 规划在服务锁之外进行，等待模型时不持锁。
- 提示词只包含人物名、描述、已授权偏好、当前设备状态和这句话；活动记录只保存来源、耗时和降级原因，不保存模型的推理过程。
- `LIVINGMIND_PLANNER_MODE` 是默认模式；每次请求可以用 `mode` 字段覆盖。规则模式下不会发出任何模型请求。

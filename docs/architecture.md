# 架构与目录（第一批实现视角）

定稿方案见 `../架构评审/LivingMind-架构评审与迁移步骤-v0.2.md`。本文件只记录**代码里实际怎么分**，以及哪些位置是后续预留。

2026-10-03 增量：原单实例模式保留；可选 `compose.gateway.yaml` + replicas 使用两 API、共享 PostgreSQL 和独立 HTTP/SQLite 虚拟网关。网关持久化状态/回执/代次，SQL 会话锁保护批次，ownerId 让启动恢复区分活跃与死亡实例；App 核对按钮只查询历史回执。详细设计、代码位置及限制见 [独立网关](durable-gateway.md)，当前验证状态见交接文档，不把本文件早期测试数量当最新结果。

## 请求链路（⑧ 起）

```text
App 对话 → POST /api/assistant/messages（人物 + 空间稳定 conversationId）
  → 主 Agent（agents/orchestrator）规则路由：休息请求 / 设备指令 / 状态查询 / 澄清 / 其他
  歧义请求：
    → 保存 PendingClarification（内存或 PostgreSQL，10 分钟）
    → 下一句话按同一会话继续原请求；取消、过期、切人物均不会误执行
  休息请求（完整分支）：
    → 人物记忆（memory/）：只取本人偏好 + 空间规则
    → Experience Agent（services/planner.py + agents/experience/）：体验目标（规则或模型，失败降级，偏离上限）
    → 能源智能（energy/）：舒适范围内的空调建议；节能模式才应用
    → Space Execution Agent（agents/space_execution/）：按设备能力和空间规则生成动作
    → Harness 预检（harness/policy.py）：生成可审计 `PolicyDecision`；白名单与参数范围；需用户确认
    → Plan（附 trace 与 energy）
  设备指令（简化分支）：主 Agent → Space Execution Agent 解析 → Harness 预检 → Plan（不经过体验与能源）
  状态查询 / 其他：直接回答，不生成动作
确认 → 绑定人/空间/计划/代次/能力的 ExecutionGrant
  → 执行器（harness/executor.py，每个动作前 guard）
  → ActionExecution 持久化状态机 → DeviceGateway V2 → 回执 + 回读 → 活动记录
```

## 请求链路（步骤 4 时的最初版本）

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
| `apps/mobile/features/shell/` | 四个入口的外壳：平板左侧导航栏、手机底部标签栏；全局提示条；对话记录按人物保存在内存 | ⑥b 实现 |
| `apps/mobile/features/chat/` | 对话主页：消息流（用户气泡、计划卡、结果卡、系统消息）、服务状态条、输入区（快捷语、语音占位、规则/模型开关）；`conversation.ts` 为纯函数 | ⑥b 实现 |
| `apps/mobile/features/me/` | 我的：本人偏好（只显示当前人物）、演示 PIN 切换、访客模式、证据面板开关、重置演示 | ⑥b 实现 |
| `apps/mobile/features/space/`、`scenes/` | 空间（设备、服务、节能占位、证据）与场景库（状态标签、人话时间线 `timeline.ts`） | ⑥b 实现 |
| `apps/mobile/features/rest/`、`devices/`、`activity/` | 业务状态 `useRestFlow`（动作返回结果）、计划卡、服务卡、设备卡、原始活动列表（只在证据面板出现） | 第一批起 |
| `apps/mobile/components/`、`theme/` | 基础组件与设计 token（颜色取自演示设计规范） | 第一批实现 |
| `apps/mobile/services/` | `api.ts` 接口定义；`http/` 真实 API；`mock/` 前端模拟 | 第一批实现 |
| `backend/app/contracts/` | Pydantic 数据契约，是前端类型的唯一来源 | 第一批实现 |
| `backend/app/api/` | HTTP 路由与统一错误格式 | 第一批实现 |
| `backend/app/rules/` | 固定休息规则 + 规则/模型共用的动作映射 | 第一批实现 |
| `backend/app/services/planner.py` | 规则/模型切换与降级 | ⑤ 实现 |
| `backend/app/agents/experience/` | Experience Agent：提示词、输出结构校验、DeepSeek Provider | ⑤ 实现 |
| `backend/app/harness/` | 统一策略评估、有界执行授权与执行器；Agent 无设备凭据 | 已进入主执行路径 |
| `backend/app/services/` | 服务生命周期（active / stopped）、确认幂等、停止失效 | 第一批实现 |
| `backend/app/adapters/virtual/` | 有状态虚拟灯光、空调、窗帘 | 第一批实现 |
| `backend/app/adapters/protocol.py`、`gateway.py` | V1 虚拟设备接口；V2 `DeviceGateway` 的设备身份、幂等动作 ID、服务代次 fencing、异步回执与错误类型 | V2 包装器已用于虚拟设备；未接 SpaceMind / 真实厂商网关 |
| `backend/app/repositories/`、`alembic/versions/0005_execution_authority.py` | 策略决策、执行授权和每个动作的持久化账本 | 内存 / PostgreSQL 两种实现已对齐 |
| `backend/app/adapters/voice.py` | 智能音箱 / 语音网关的转写、来源、说话人/空间提示、播报与取消协议 | 接口预留，未接语音 |
| `backend/app/adapters/events.py` | 真实传感器事件 ID、去重键、来源、空间与采集时间协议 | 接口预留，未接传感器 |
| `backend/app/repositories/` | 内存 / PostgreSQL 两种业务事实存储；含待澄清状态 | 已实现 |
| `backend/app/demo/` | 种子人物、空间、演示账户 | 第一批实现 |
| `packages/api-client/` | 由 OpenAPI 生成的 TS 类型 | 第一批实现 |
| `backend/app/agents/orchestrator/` | 主 Agent：规则路由、编排、协作轨迹（AgentStep）、事件调整编排 | ⑧ 实现 |
| `backend/app/agents/space_execution/` | Space Execution Agent：设备能力、空间规则（夜间灯光上限）、休息动作、调整动作、设备指令解析（规则） | ⑧ 实现 |
| `backend/app/memory/` | 人物记忆：本人偏好（可编辑，访客不可）、空间共享规则；共享列表不含任何人的偏好 | ⑧ 实现 |
| `backend/app/energy/` | 能源智能（在线规则）：舒适范围、分时电价、估算负荷档位、舒适优先 / 节能模式 | ⑧ 实现 |
| `backend/app/energy/simulation.py` | 只读加载给定的固定日离线仿真 JSON，绝不加载 torch/gym 或写设备 | P07 迁入 |
| `simulation/home-energy/` | 家庭能源研究快照、模型权重、给定指标与溯源；与 App 运行时隔离 | P07 迁入 |
| `backend/app/harness/policy.py` | 规划阶段预检（与执行器同一套白名单和范围） | ⑧ 实现 |
| 事件入口与调整（`services/rest_service.py::inject_event`、`rules/rest_rule.py::adjustment_rule`） | 一次事件调整 | ⑥ 实现 |
| 真实后台定时器、SpaceMind / 厂商 Adapter、语音网关 | 真实部署接入 | **未实现**；目前只有模拟时钟与接口预留 |

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
9. 默认内存模式重启即重置；配置 PostgreSQL 后，人物偏好、计划、服务、步骤、活动和待澄清状态可恢复。`POST /api/demo/reset` 可手动重置。
10. 计划一经确认即标为 `executed`，表示“已被采纳”；每个动作的真实结果以 `results` 为准。执行过程中重复确认，返回的是当时已完成的部分。
11. 同一演示账户下的任何人物都能停止空间里正在运行的服务，不要求是发起人。这是有意的：共享空间里，谁都应该能让设备停下来。
12. 模型计划相对本人偏好的偏离有上限：灯光与窗帘 ±40、空调 ±3°C（`services/planner.py` 的 `MAX_DEVIATION`）；超出即改用规则计划并标注原因。这是“体验是约束”在代码里的落点，由后端强制，不只靠提示词。
13. 未预期的异常统一返回 `INTERNAL_ERROR`（500），不暴露堆栈；详细信息只写服务器日志。
14. App 等待计划的时间 = 后端模型超时 + 3 秒（从 bootstrap 读取），避免 App 先于后端放弃；事件请求同样；其他请求仍是 8 秒。
15. 事件只调整正在运行的服务：没有服务、上一次调整未结束、达到次数上限（默认 3）、冷却中（默认 30 秒）都会忽略并记录原因。每个服务同时只有一个调整在进行。
16. 事件的规则调整：室温偏离空调设定 2°C 以上时，空调每次调 1°C，且不超出本人偏好 ±3°C；灯光和窗帘不动。模型调整只执行与当前状态不同的项，仍受偏离上限约束。
17. 事件调整跟随服务的计划模式（`Service.plannerMode`）：规则模式启动的服务，事件时也不调用模型。
18. 调整次数在执行前计数；执行中被停止，剩余动作跳过，已开始的那一个不撤销。
19. 慢模型请求开始时记录空间 epoch；若规划期间服务被停止，返回的计划直接标为 `invalidated`，不能再确认启动新服务。
20. 同一服务的自动操作互斥：夜间时钟步骤进行时，环境事件记录为“整晚安排正在执行”；环境调整进行时，时钟不推进。两者不会并发写设备。
21. 确认时把计划的语义哈希、人物、空间、版本、服务代次和允许能力固化为 `ExecutionGrant`；授权只能取平台策略与设备能力的交集。一次性指令锁定到确认的具体数值，不能用同一授权改发其他数值。
22. 每个动作都有独立账本：`pending → dispatching → accepted → completed/failed/rejected/unknown/cancelled`；已受理但无终态回执的动作标记为 `unknown`，重启后不盲目重放。
23. `actionId` 在网关内先占位再写设备，并发重试不会重复写；同 ID 不同载荷会被拒绝。停止或重置提升 fencing 代次，旧代次命令在网关层写设备前被拒绝。

## 模型调用边界（⑤）

- 模型只生成体验目标和三个数值；输出先过 Pydantic 结构与范围校验，再变成普通 `Plan`，确认后走同一个执行器。模型不能直接写设备。
- 规划在服务锁之外进行，等待模型时不持锁。
- 提示词只包含人物名、描述、已授权偏好、当前设备状态和这句话；活动记录只保存来源、耗时和降级原因，不保存模型的推理过程。
- `LIVINGMIND_PLANNER_MODE` 是默认模式；每次请求可以用 `mode` 字段覆盖。规则模式下不会发出任何模型请求。

## 前端结构（⑥b）

- 导航用组件内状态切换四个入口，没有引入 Expo Router；以后需要深链接时再换。
- 所有入口共用一个 `useRestFlow`；对话内容只在前端内存，按人物分开保存，刷新即清空。
- 计划卡只有“最新且与当前计划一致”的那一张可以确认，其余是历史。
- 原始活动记录只在“我的 → 证据面板”和空间页（证据面板打开时）出现；对话和场景里用人话。

## 身份（⑥b 补充）

- `POST /api/persons/{personId}/unlock` 校验演示 PIN，只用于共享平板防误切换；不签发令牌，后续请求不据此授权；PIN 不会出现在任何接口返回里。
- 访客 `person-guest` 使用空间默认设置，没有 PIN；计划摘要与说明都写明“访客”。
- `GET /api/scenes` 返回场景库，状态与实现一致，由测试守护。

## ⑧ 补充规则

21. 主 Agent 的路由是规则（关键词），在协作过程里标为“规则”；只有 Experience Agent 会调用模型，每条消息最多一次。
22. 共享列表（bootstrap）不含任何人的偏好；`GET /api/memory` 只返回请求人物自己的偏好和空间规则。演示身份下这由请求上下文决定，不是认证。
23. 偏好编辑：访客不可编辑；灯光不超过空间规则 60%；数值范围由契约校验；改动写入活动记录，下一次计划立即使用。
24. 能源智能：舒适范围 = 体验目标 ±1°C；高峰电价（本地 18–23 点，可用 `LIVINGMIND_DEMO_LOCAL_HOUR` 固定）且需要制冷时，建议把空调提高 0.5°C；“舒适优先”只给建议，“节能模式”才应用。负荷是规则估算，只显示档位和 kW 估算，不显示节省比例或金额。
25. 设备指令走简化分支，确认后执行但**不创建休息服务**；休息服务运行中也可以下设备指令；停止服务会让未确认的设备指令失效。
26. 事件调整也由主 Agent 编排（体验 → 执行 → Harness），以舒适优先，不应用节能策略。
27. 否定、冲突或指代不清的请求先澄清，不生成计划或设备动作；待澄清状态按账户、人物、空间和 `conversationId` 隔离，10 分钟过期。
28. PostgreSQL 启动恢复会清理崩溃遗留的执行标记，并取消结果未知的 `running` 步骤，避免盲目重放。`GET /api/system/recovery` 暴露本次恢复结果；虚拟设备状态仍不跨进程恢复。

## ⑦ 整晚服务规则

27. 休息计划附带整晚安排（`Plan.schedule`，Space Execution Agent 用规则生成，Harness 预检），随计划一起确认；设备指令与事件调整没有整晚安排。起床时间限制为演示选项 06:30 / 07:00 / 07:30。
28. 整晚安排跑在**模拟时钟**上（22:30 起），只由 `POST /api/services/{id}/clock/advance` 推进（`minutes` 为空 = 跳到下一步）；`POST /api/services/{id}/sleep` 是明确的模拟入睡信号，只推进首个入睡步骤。后端不读真实时间、不开后台定时器。App 的“自动播放”只是每 2.5 秒调用一次推进接口。
29. 每一步在锁内先由 `pending` 改为 `running` 再执行，所以最多执行一次；同一服务同时只允许一个推进，第二个请求直接返回“上一次推进仍在进行”。写设备仍经过执行器，每个动作前重查服务状态与代次。
30. 停止服务时，未执行的步骤改为 `cancelled`；正在执行的推进在下一个动作前被拦下，剩余步骤也记为 `cancelled`。已开始的那个动作不撤销。
31. 只有每个到点步骤的全部设备动作都成功，服务才会变为 `completed`；任一步里的任一动作失败、被拒绝或被跳过，该步即取消，整晚服务最终为 `failed`。两者都保持设备当前状态；之后的推进返回 `SERVICE_NOT_ACTIVE`，事件被忽略，可以开始新的休息服务。
33. 演示重置会同时提升空间代次与虚拟设备代次；重置前已经离开服务锁、仍在等待设备的旧请求，返回后也不能再改写新状态。设备写入成功但回读失败时，执行器返回明确的动作失败结果。
32. 深夜步骤把空调调高 1°C，但不超出本人偏好 +3°C；唤醒分三步（所选起床时间前 30 / 15 / 0 分钟），空调回到当晚目标，灯光最高 60%（空间规则）。
33. `GET /api/spaces/{spaceId}/energy/simulation` 只返回给定的离线固定日仿真证据；它不进入规划、Agent、Harness 或执行器路径。MATD3 在该给定结果中只有一个智能体，不能表述为多智能体协同或实时控制。
34. 单个低风险设备动作（灯、空调、窗帘）从设备面板直接执行，不弹确认框，改为 5 秒可见倒计时的撤销窗口；撤销是反向写入记录下来的原值，不是猜一个相反指令。多动作的休息计划仍然先确认后执行。撤销窗口只在进程内，重启后没有东西可撤销。
35. “直接控制”只是没有对话框，不是没有检查：仍走同一个执行器——白名单、参数范围、代次 guard、写入、回读。
36. 语音只负责把话变成同一条 assistant-message 输入；采集、识别、执行是三件事，任何超时的默认结果都是不执行。没有真实识别器时，转写文本必须带来源标签，且界面不得出现“识别”字样。
37. LangGraph 的检查点连接由 psycopg 自行持有，不受 SQLAlchemy 连接池设置管辖，因此每进程只建一个、按数据库 URL 缓存共享（`PostgresSaver` 自带线程锁）。编排器实例不得各开一条，否则一次测试运行就能耗尽 PostgreSQL 的 `max_connections`。

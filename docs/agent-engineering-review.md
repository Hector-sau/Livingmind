# Agent 架构评审与工程落地说明

更新：2026-09-19。本文用于评委展示、面试解释和后续接入评审；能力口径以当前代码和测试为准。

## 1. 架构判断

LivingMind 是一个受控的混合式 Agent 系统：主 Agent 负责路由和编排，Experience Agent 可调用 DeepSeek 生成结构化体验目标，Space Execution Agent 用确定性规则把目标转换成设备动作。能源策略、Memory、Harness 和 Executor 是共享能力，不把类名或中间件数量包装成更多 Agent。

```text
平板 / 未来语音入口
  → 主 Agent：意图路由；歧义时进入可恢复澄清状态
  → Memory：当前人物偏好 + 空间规则
  → Experience Agent：规则或 DeepSeek → Pydantic 结构化体验目标
  → Energy Intelligence：舒适范围内给出或应用节能建议
  → Space Execution Agent：查询能力 → 设备动作 + 整晚安排
  → Harness：PolicyDecision（白名单、参数范围、模型偏离上限）
  → 用户确认
  → ExecutionGrant：绑定人物 / 空间 / 计划哈希 / 服务代次 / 允许能力
  → Executor：每个动作前重查 → ActionExecution 账本 → DeviceGateway 回执与回读
  → 服务状态 / 事件 / 模拟时钟 → 调整、完成或停止
```

## 2. 各项能力范围

| 能力 | 已实现 | 当前边界 |
|---|---|---|
| 主 Agent | 休息、设备指令、状态查询、范围外回答；否定、冲突和指代不清识别；协作轨迹 | 规则路由，不能理解任意开放任务 |
| 多轮澄清 | 待澄清状态按账户、人物、空间、会话隔离；10 分钟过期；补充后继续；可取消；内存或 PostgreSQL | 限定场景；不是通用对话记忆 |
| Experience Agent | DeepSeek JSON 输出、Pydantic 校验、偏好偏离限制、超时及非法输出降级 | 只生成体验目标；当前只有一次真实模型延迟样本 |
| Space Execution Agent | 灯、空调、窗帘的能力过滤、动作映射、直接指令解析和整晚步骤 | 当前是规则模块；设备类型仍限定为三类 |
| Memory | 本人休息偏好、访客默认值、共享空间规则；PostgreSQL 可持久化 | 不从对话自动学习；没有向量检索或历史反馈总结 |
| Harness / Executor | 可审计策略决策、有界执行授权、动作白名单/范围、逐动作 guard、持久化状态转移、回执与回读 | 演示身份检查不是生产认证；已发出的硬件动作无法由停止撤销 |
| 持续服务 | 模拟入睡、室温事件调整、冷却/次数上限、整晚步骤、停止、失败状态 | 事件和时钟均为模拟；没有真实传感器或后台调度器 |
| 能源 | 在线解释性规则；离线固定日 MATD3 结果展示 | MATD3 不在线控制，固定日结果不能外推 |
| LangGraph | 可切换的规划图、节点轨迹、内存/PostgreSQL checkpoint、与 legacy 等价测试 | checkpoint 当前用于流程记录和调试，不宣称 HTTP 崩溃后自动续跑 |
| 启动恢复 | PostgreSQL 业务事实恢复；清理崩溃遗留 flag；已 dispatch/accepted 但无终态的动作标记 `unknown`、不盲目重放；状态可查询 | 虚拟设备状态在进程内，未完成真实硬件回读对账 |

## 3. 接入接口

| 接口 | 当前契约 | 接入要求 |
|---|---|---|
| 设备底座 V1 | `DeviceAdapter`：能力、状态、写入、回读 | 当前虚拟设备正在使用；适合演示和同类设备适配 |
| 设备底座 V2 | `DeviceGateway`：`deviceId`、`actionId`、`serviceEpoch`、受理/完成/失败/拒绝/未知回执、观测时间和错误类型 | 虚拟设备包装器已进入主执行路径，实现 actionId 幂等和过期 serviceEpoch 拒绝；SpaceMind / 厂商对端未接入 |
| 智能音箱 | `VoiceGateway`：转写、来源、音频 ID、说话人/空间提示、播报和取消 | ASR、唤醒词、人物授权映射与硬件播报待接入 |
| 环境事件 | `EnvironmentEventAdapter`：事件 ID、去重键、来源、空间、采集时间、类型和值 | 真实传感器网关待接入；演示 HTTP 注入仍标注 simulated |
| 模型 | `ChatProvider.complete_json()` | 可增加兼容 Provider；必须保留结构校验、超时和规则降级 |
| 事件总线 | `EventPublisher.publish()` | 当前 PostgreSQL 队列已实现；Kafka 只需实现该边界并完成 broker 联调后才能宣称接入 |

## 4. 工程安全语义

1. 规划不写设备，必须由用户确认。
2. 模型只输出结构化目标，不能调用设备 Adapter。
3. 确认生成短期、有界的 `ExecutionGrant`，授权只能缩小平台策略；Agent 和 LangGraph 都不持有设备凭据。
4. 每个设备动作依次经过服务/代次 guard、平台策略、授权范围、持久化账本、网关幂等、写入和回读。
5. 停止撤销授权并提升空间 fencing 代次；旧代次命令在网关层被拒绝。已经开始的单个外部动作仍不承诺撤销。
6. PostgreSQL 是业务事实来源；Redis 只做短锁和冷却加速，故障时回到数据库约束。
7. Outbox 保存异步业务事件，不承载设备控制命令。
8. 崩溃时处于 `dispatching/accepted` 且结果不明的动作不会自动重放；启动恢复将其标记为 `unknown` 并通过 `/api/system/recovery` 暴露数量。

## 5. 评委演示路径

1. 输入“把那个调低一点”：展示系统先澄清，设备状态不变。
2. 回答“灯调到 20%”：展示同一会话恢复为设备计划，并等待确认。
3. 输入“我不想休息，只想关灯”：展示否定语义进入设备指令分支。
4. 输入“我想休息”：展示人物记忆、Experience、Energy、Space Execution、Harness 的真实协作轨迹。
5. 确认后展示动作结果和设备回读；再注入模拟室温事件并停止服务。
6. 查看 `/api/system/recovery`，说明数据库恢复与真实设备恢复为什么必须分开。

## 6. 可说与不可说

可以说：限定 Home Living 场景的 1+2 混合式 Agent 编排；一次真实 DeepSeek 结构化计划调用；可恢复澄清；人物偏好隔离；基于 PolicyDecision + ExecutionGrant + 动作账本 + Gateway fencing 的受控执行；PostgreSQL、LangGraph、Redis、Outbox、Docker 与 CI 均有实际代码和测试。

不能说：三个大模型 Agent；任意自然语言任务；生产级身份认证；真实语音、传感器或 SpaceMind 已接入；LangGraph 能自动恢复所有中断；Redis 锁保证真实设备恰好执行一次；MATD3 正在在线节能。

## 7. 后续真实接入门槛

- SpaceMind 文档和测试环境到位后，用真实对端替换 `AdapterDeviceGateway`，保持现有 `DeviceGateway` 契约，重跑异步回执、重复 `actionId`、过期 `serviceEpoch` 和状态回读测试。
- 接入真实语音前，明确说话人到 `accountId/personId/spaceId` 的授权规则。
- 多 API 实例控制真实设备前，把已在虚拟网关验证的 `serviceEpoch` fencing 下沉到真实网关，并根据最长硬件命令时间补锁续租。
- 后台定时服务上线前，将模拟时钟替换为可恢复调度器，并验证时区、漏触发和重复触发。
- 真机与真实硬件验证完成后，再更新证据表中的“接口预留/模拟”状态。

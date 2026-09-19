# LivingMind 技术架构与上手指南

更新：2026-09-19

这份文档用于回答三类问题：项目实际用了什么技术、每项技术解决什么问题、后续怎样把演示原型升级成可持续维护的真实工程。

> 状态纪律：本文件同时描述“当前实现”和“目标实现”。写进目标架构不等于已经完成；只有代码、测试和运行证据齐全后，才能把状态改为“已实现”。

## 1. 架构结论

LivingMind 采用“移动端 + API + Agent 规划 + 安全执行 + 数据与事件基础设施”的分层架构。

```text
iPad / Android App                          未来语音入口
       │                                         │
       └────────────── assistant contract ───────┘
                              │
                        FastAPI API
                              │
                    LangGraph Planning Graph
                              │
     ┌──────────────┬─────────┼───────────┬──────────────┐
     │              │         │           │              │
   Memory      Experience   Energy   Space Execution   Harness
 PostgreSQL       Agent      Rules        Agent         Precheck
     │              │         │           │              │
     └──────────────┴─────────┴───────────┴──────┬───────┘
                                                 │
                                           proposed Plan
                                                 │
                                      用户确认 / RestService
                                                 │
                              PolicyDecision → ExecutionGrant
                                                 │
                         Executor → ActionExecution ledger
                                                 │
                          DeviceGateway (idempotency + fence)
                                                 │
                            虚拟设备 / 未来 SpaceMind / 厂商底座

PostgreSQL：业务事实、人物记忆、计划、服务、动作、Outbox、Graph checkpoint
Redis：短期锁、冷却、幂等加速、热点状态；不可作为唯一事实来源
事件总线：动作完成后的领域事件、审计投影、分析；默认用 PostgreSQL 队列实现，Kafka 为可选实现；都不在设备控制关键路径
Docker Compose：在开发机和 CI 中统一启动 API、数据库、缓存和 Worker；消息中间件放在可选 profile，默认不启动
```

设计原则：

1. 模型只生成体验目标，不能直接控制设备。
2. LangGraph 负责理解和规划；`RestService + Harness + Executor + DeviceGateway` 负责确认、有界授权、停止和执行安全。Agent 和 Graph 不持有设备凭据。
3. PostgreSQL 是唯一事实来源（source of truth）。
4. Redis 丢失后系统应能降级运行，不能丢失人物偏好或服务事实。
5. 事件总线故障不能阻止“确认、停止、设备执行”；待发送事件保存在 PostgreSQL Outbox。
6. 所有消费者按 `event_id` 幂等，不能假设消息绝不会重复。
7. Expo 原生开发继续在 Mac 运行；Docker 主要承载后端和基础设施。
8. 后端保持**同步**技术栈（同步路由 + 同步驱动 + 线程池）。要改成异步必须整条链路一起改，单独立项，不在 T1–T6 内混做。
9. 本文中标为“已实现”的目录、表名和 Key 已落到代码；标为“待实现”的内容仍是设计目标，最终以代码与验证记录为准。

## 2. 当前实现与目标实现

| 能力 | 当前实现 | 目标实现 | 状态 |
|---|---|---|---|
| 移动端 | Expo / React Native / TypeScript | 保持；连接容器化 API | 已实现 |
| API | FastAPI + Pydantic | 保持；增加 lifespan 资源管理和基础设施健康检查 | 已实现，待扩展 |
| Agent 编排 | legacy顺序编排与LangGraph `StateGraph` 两条可切换路径，共用阶段方法 | 保持等价对照与checkpoint恢复 | 已实现规划分支 |
| Experience Agent | DeepSeek Provider；结构化输出；失败降级 | 作为 LangGraph 节点复用 | 已实现 |
| 人物记忆 | `MemoryService` + 内存/SQL两种Repository，按人物与空间隔离 | 继续完善认证与权限边界 | PostgreSQL持久化已实现 |
| 运行状态 | 内存/SQL 两种 Store；计划、服务、策略决策、执行授权、动作账本、步骤、活动与代次可落库 | 真实设备观测状态仍由 Gateway 负责 | PostgreSQL 持久化已实现 |
| 并发控制 | Python锁、PostgreSQL约束与行级认领、Redis空间锁/冷却 | 生产级多机压测仍是后续项 | 本地组合与降级已验证 |
| 设备 | 有状态虚拟 Adapter + `AdapterDeviceGateway`；`actionId` 幂等、`serviceEpoch` fencing、回执/回读 | 保持 `DeviceGateway` Protocol，替换为真实 SpaceMind / 厂商对端 | 虚拟 V2 路径已实现；真实对端未接入 |
| 能源 | 在线规则 + 离线固定日仿真 | 保持边界；事件进入 Kafka 分析流 | 已实现规则与只读展示 |
| 异步事件 | PostgreSQL Transactional Outbox → 数据库队列 → 幂等Consumer Projection；活动仍同步写入 | Kafka仅保留可选接口 | 已实现数据库队列 |
| 语音入口 | `adapters/voice.py` 只有接口定义，没有任何调用方 | 真实网关返回文本与来源后走同一 assistant 契约 | **仅接口预留，未实现** |
| 容器化 | Python 3.12多阶段非root镜像 + Compose | 保持可复现冻结 | 宿主机全栈与容器E2E通过 |
| CI | 三套后端matrix、迁移升降、TS、契约、Docker E2E | 后续提交持续保持全绿 | GitHub Actions 最新运行 `35409969801`（`bfcdd0e`）：6/6 Job 通过 |

## 3. 1+2 Agent 与 LangGraph

### 3.1 Agent 分工

| 模块 | 责任 | 是否调用模型 |
|---|---|---|
| Main Agent / Orchestrator | 识别意图、选择分支、组织节点、汇总轨迹 | 否，首版使用确定性路由 |
| Experience Agent | 把“我想休息、有点热”变成体验目标 | 可选调用 DeepSeek |
| Space Execution Agent | 把体验目标转换成设备动作和整晚安排 | 否，规则与设备能力驱动 |
| Energy Intelligence | 在舒适边界内给出能源建议 | 否，当前为规则 |
| Harness | 白名单、范围、确认、停止、执行前检查 | 否，确定性安全层 |

当前实现位置：

```text
backend/app/agents/orchestrator/
backend/app/agents/experience/
backend/app/agents/space_execution/
backend/app/energy/
backend/app/harness/
```

### 3.2 目标 Graph

```text
START → route_intent
  ├─ rest → load_memory → experience → energy → space_execution → harness → build_plan → END
  ├─ device_command → read_device → space_execution → harness → build_plan → END
  ├─ status → read_device → direct_answer → END
  └─ other → capability_answer → END
```

建议新增：

```text
backend/app/graph/
├── state.py          # LivingMindState TypedDict / Pydantic schema
├── builder.py        # StateGraph、节点和条件边
├── nodes/
│   ├── route.py
│   ├── memory.py
│   ├── experience.py
│   ├── energy.py
│   ├── execution_plan.py
│   └── harness.py
└── runtime.py        # compile、checkpointer、thread_id
```

`LivingMindState` 至少包括：

```text
request_id, account_id, person_id, space_id
utterance, intent, planner_mode
person_context, device_state
experience_target, energy_advice
device_actions, night_schedule
trace, fallback_reason, plan
```

`thread_id` 建议使用：

```text
account:{account_id}:person:{person_id}:space:{space_id}:conversation:{conversation_id}
```

LangGraph checkpoint 是“工作流执行记忆”，人物偏好是“产品记忆”，两者不能混用。生产目标使用 PostgreSQL checkpointer；内存 saver 只用于单元测试。

checkpoint 的表由 checkpointer 自己创建（`setup()`），**不归 Alembic 管**。启动流程必须显式调用一次初始化，否则只有在第一次请求时才会暴露缺表问题。checkpointer 与 LangGraph 的版本要一起锁定。

“legacy 与 graph 生成等价 Plan”不能按字面逐字段相等验收（`plan_id`、`action_id`、时间戳、`latency_ms` 必然不同）。等价的定义是：

```text
比较：intent、summary、notes、source、fallback_reason、
     actions（device/command/value/label 顺序一致）、
     schedule（at/phase/title/每步 actions）、
     energy（模式、电价档、建议温度、是否应用）、
     trace（agent 名称与顺序）
忽略：所有 id、created_at/expires_at、latency_ms、trace 内的耗时
```

对照器实现为一个可在测试里直接调用的函数，并配一个脚本对固定输入集跑双路径比对。

设备执行不放入可随意重放的规划节点。Graph 输出普通 `Plan` 后仍走现有确认接口、计划幂等、服务 epoch、Executor 和设备回读。

## 4. PostgreSQL：唯一事实来源

### 4.1 负责什么

PostgreSQL 保存不能因进程重启而丢失的业务事实：

- 账户、人物、空间与成员关系。
- 每个人物独立的偏好记忆。
- 计划、版本、来源和 Agent trace。
- 服务生命周期和整晚步骤。
- 设备动作与回读结果。
- 活动记录。
- 能源模式。
- Kafka Outbox 事件。
- LangGraph checkpoint（独立 schema，由 saver 管理）。

### 4.2 建议数据表

```text
accounts
persons
spaces
space_memberships
person_preferences
space_rules
plans
services
scheduled_steps
device_actions
action_results
activity_records
outbox_events
consumer_receipts
```

关键约束：

- `person_preferences`：唯一键 `(person_id, space_id)`。
- `plans`：唯一键 `(plan_id, version)`。
- `services`：同一空间最多一个 `status='active'` 的部分唯一索引。
- `action_results`：`action_id` 唯一，重复确认不能重复插入或执行。
- `outbox_events.event_id`：UUID 主键。
- 所有业务表记录 `created_at`、`updated_at`；需要并发更新的表增加 `version`。

### 4.2.1 现有并发语义如何落到数据库

当前正确性依赖三件进程内的东西，迁移时必须逐条找到数据库对应物，否则并发测试会失去意义：

| 现在的机制 | 作用 | 数据库表达 |
|---|---|---|
| `RLock` 保护簿记 | 同一时刻只有一个写者 | 事务 + `SELECT … FOR UPDATE` 锁定计划行 / 服务行 |
| 单空间单服务 | 不会同时开两个休息服务 | `services` 上 `status='active'` 的部分唯一索引，插入冲突即为“已有服务” |
| 空间代次 epoch | 停止后让旧计划与旧任务失效 | `spaces.epoch` 列；计划记录创建时的 epoch，执行前比对；停止时 `epoch = epoch + 1` |
| 设备代次 | 重置后隔离旧任务的迟到写入 | `spaces.device_epoch` 列，语义同上 |
| 夜间步骤认领（pending → running） | 每步最多执行一次 | `UPDATE scheduled_steps SET status='running' WHERE step_id=:id AND status='pending' RETURNING step_id`，没有返回行就说明别人已经领走 |
| 事件冷却 30 秒、调整次数上限 | 限制自动调整频率 | 写在 `services.last_adjusted_at` 与 `services.adjustments`，在同一事务里判断并自增；Redis 只是加速，不是唯一依据 |

迁移时保留现有并发测试的断言，只替换底层实现；测试从“单进程多线程”扩展为“多连接并发事务”。

### 4.3 如何实现

建议使用：

- SQLAlchemy 2.x（**同步 API**）：ORM、事务、连接池。
- psycopg 3 同步驱动：与现有同步路由和线程池一致，不引入 async 混用。
- Alembic：数据库结构迁移，每个 schema 变化必须有 migration。
- Repository Protocol：业务服务不直接写 ORM，方便测试时替换成内存实现。

依赖版本必须锁定。当前 `backend/requirements.txt` 用的是 `>=` 范围，容器每次构建可能装到不同版本；T1 起增加 `constraints.txt`（或锁文件），把 FastAPI、SQLAlchemy、Alembic、psycopg、redis、LangGraph 与 checkpointer 固定到具体版本。

建议目录：

```text
backend/app/db/
├── session.py
├── models/
├── repositories/
└── unit_of_work.py
backend/alembic/
```

一次“确认计划”的数据库事务应完成：

1. 锁定计划行并检查版本和状态。
2. 检查该空间没有其他活跃服务。
3. 把计划改为 `executed`。
4. 创建服务、步骤和待执行动作记录。
5. 写入 `plan.confirmed` Outbox 事件。
6. 提交事务。
7. 在事务外调用设备；每个结果再以独立幂等事务写回。

演示重置（`POST /api/demo/reset`）在数据库下的语义要显式定义，否则会出现“清不干净”或“误删”：

```text
一个事务内：按 accountId 删除该演示账户的计划、服务、步骤、动作、活动与 Outbox 行
          → 重置该账户空间的设备状态、能源模式、epoch
          → 重新写入种子偏好
```

重置只影响演示账户，且必须有单独测试：重置后活跃服务为空、偏好回到种子值、旧计划不能再被确认。

### 4.4 人物记忆

人物偏好仍由 `MemoryService` 提供领域接口，但底层从字典改为 Repository：

```text
MemoryService
  → PersonPreferenceRepository
      → PostgreSQL person_preferences
```

首版只保存明确编辑的偏好，不自动从对话推断事实。以后若增加自动记忆，应新增“候选记忆 → 用户确认 → 正式写入”，不能让模型静默修改画像。

## 5. Redis：短期状态与分布式协调

### 5.1 负责什么

Redis 只保存可过期、可重建的数据：

- 同一空间的短期规划锁和执行协调。
- 环境事件 30 秒冷却。
- 每个服务的调整次数快速计数。
- API 幂等结果的短期缓存。
- 热点设备状态缓存。
- 将来 WebSocket / SSE 的短期广播。

Redis 不保存唯一的人物偏好、计划事实或最终设备结果。

### 5.2 Key 设计

```text
lock:space:{space_id}:planner                 TTL 10s
lock:space:{space_id}:executor                TTL 30s
cooldown:service:{service_id}:room_temp       TTL 30s
counter:service:{service_id}:adjustments      TTL = service lifetime
idem:plan:{plan_id}:version:{version}         TTL 24h
device:space:{space_id}:snapshot              TTL 30s
```

锁的 value 必须是随机 token，释放时只能删除 token 与自己一致的锁；数据库约束和 `version/epoch` 仍是最终防线。Redis 不可用时回退到 PostgreSQL 锁和查询，性能下降但核心控制仍可运行。

### 5.3 如何实现

- 使用 `redis-py` 的**同步**客户端，与后端同步栈保持一致（异步化是独立项目，不在 T1–T6 内）。
- 在 FastAPI lifespan 创建一个共享连接池，关闭应用时统一释放。
- 所有非关键缓存访问捕获连接错误并降级到 PostgreSQL。
- 冷却和计数使用带 TTL 的原子命令或 Lua 脚本，避免“先读再写”的竞态。

建议目录：

```text
backend/app/cache/
├── client.py
├── keys.py
├── locks.py
└── cooldown.py
```

## 6. 领域事件：Outbox 与事件总线（Kafka 可选）

### 6.1 要解决什么问题

需要把“已经发生的事实”交给不应该阻塞主请求的下游：

- 审计与活动流投影。
- Agent / 模型耗时分析。
- 能源统计与演示数据汇总。
- 未来的通知、主动服务触发器和设备遥测消费。

**当前项目实际上还没有这个问题**：只有一个后端进程、一个消费方（App 读活动记录）。因此本阶段的目标不是“部署一个消息中间件”，而是把**事务一致性与异步分发的模式**做对，并留出可替换的实现。

事件总线不用于同步发送“现在关灯”。确认、停止、执行和回读必须通过当前同步控制链路返回明确结果。

**活动记录仍然同步写入 PostgreSQL**，App 的证据面板读的就是这张表。事件投影只是它的异步副本与分析视图；绝不能把活动记录改成“等消费者投影出来再显示”，否则演示时会出现记录延迟或缺失。

### 6.2 事件总线的两种实现

对外只暴露一个接口：

```text
EventPublisher.publish(batch: list[Envelope]) -> list[event_id]   # 已成功发出的
```

| 实现 | 何时用 | 代价 |
|---|---|---|
| `PostgresQueuePublisher`（默认） | 日常开发、CI、演示 | 不额外占内存；队列就是 `outbox_events` 表本身，消费者用 `FOR UPDATE SKIP LOCKED` 领取 |
| `KafkaPublisher`（可选） | 想演示或验证 Kafka 时 | 单节点 KRaft 常驻约 1 GB 内存；放在 Compose 的 `kafka` profile，默认不启动 |

这样“至少一次投递、按 `event_id` 幂等、重试与死信、按空间保序、多实例竞争消费”这些真正值钱的部分在默认实现里就完整存在；Kafka 只是换一个 sink，验证过一次后即可保持关闭。对外口径必须如实：默认用数据库队列，Kafka 已验证/未验证要写清楚。

### 6.3 Topic / 通道设计

首版只建少量稳定通道，两种实现共用同一组名字：

```text
livingmind.domain-events.v1
livingmind.device-telemetry.v1       # 有真实设备遥测后启用
livingmind.dead-letter.v1
```

领域事件类型：

```text
plan.created
plan.confirmed
service.started
service.adjusted
service.stopped
service.completed
service.failed
device.action.completed
memory.preference.updated
energy.mode.updated
```

统一事件 envelope：

```json
{
  "eventId": "uuid",
  "eventType": "service.started",
  "schemaVersion": 1,
  "occurredAt": "ISO-8601",
  "accountId": "demo-account",
  "personId": "person-lin",
  "spaceId": "space-home-bedroom",
  "aggregateId": "svc-00001",
  "correlationId": "request-uuid",
  "payload": {}
}
```

顺序按 `spaceId` 保证：Kafka 用它作 message key（同一空间进同一分区）；数据库队列实现按 `spaceId` 分组、按自增序号顺序领取。

### 6.4 Transactional Outbox

不能先写 PostgreSQL、再直接发事件；如果进程在两步之间崩溃，会出现数据库成功但事件丢失。采用 Transactional Outbox：

```text
业务事务：更新 service + 插入 outbox_events
                         ↓
Outbox Publisher：读取未发送行 → EventPublisher.publish → 标记 published_at
                         ↓
Consumer：按 event_id 幂等处理 → 写 consumer_receipts
```

Publisher 使用 `FOR UPDATE SKIP LOCKED` 领取任务，可运行多个实例。无论哪种实现都按至少一次设计消费者，重复消息是正常情况，必须用 `event_id` 去重。

建议目录：

```text
backend/app/events/
├── envelope.py
├── outbox.py
├── publisher.py        # EventPublisher 协议 + Postgres 队列实现
├── kafka_publisher.py  # 可选实现
└── topics.py
backend/workers/
├── outbox_publisher.py
├── activity_projector.py
└── energy_analytics.py
```

总线不可用时（Kafka 停机，或数据库队列积压）：

- API、停止和设备控制继续工作。
- Outbox 行保持 `pending`。
- Publisher 指数退避重试。
- 超过重试阈值后写告警，但不删除事件。
- 恢复后补发；消费者幂等处理。

## 7. Docker Compose：可复现运行环境

### 7.1 服务组成

```text
默认启动：
  api                 FastAPI + LangGraph + 业务服务
  postgres            业务数据 + LangGraph checkpoint
  redis               缓存、锁、冷却
  outbox-worker       Outbox → 事件总线（默认数据库队列）
  activity-projector  事件 → 活动流投影

profile: kafka（默认不启动，仅在需要验证 Kafka 时开启）
  kafka               KRaft 单节点
  kafka-init          创建 Topic 后退出
```

每个阶段只加入当前代码真正用到的服务；端口一律绑 `127.0.0.1`，不要暴露到局域网（App 连的是 API 的 8000 端口，由 README 的局域网说明单独处理）。

Expo Metro、iOS 模拟器和真机调试继续在 Mac 上运行，不进入 Linux 容器。App 通过 `http://<Mac 局域网 IP>:8000` 访问映射出来的 API。

建议新增：

```text
compose.yaml
.dockerignore
backend/Dockerfile
backend/Dockerfile.worker
```

`.dockerignore` 至少排除：`.git/`、`apps/`（含 `node_modules`）、`packages/`、`dist/`、`docs/`、`simulation/`、`**/.venv/`、`**/__pycache__/`、`apps/mobile/e2e/.out/`。仓库里有约 28 MB 的仿真权重和图片、几百 MB 的前端依赖，不排除会让构建上下文无谓变大。

容器启动顺序依赖健康检查，不依赖固定 sleep：

```text
postgres healthy ─┐
redis healthy ────┼→ migration → api healthy
kafka healthy ────┘                │
                                   ├→ outbox-worker
                                   └→ activity-projector
```

密钥只通过 `.env` 或部署平台 Secret 注入；`.env`、模型 key、数据库密码不能 COPY 进镜像或提交 Git。

## 8. 一次“我想休息”的完整数据流

1. App 调用 `POST /api/assistant/messages`，携带 `accountId/personId/spaceId`。
2. API 创建 `request_id` 和 LangGraph `thread_id`。
3. Graph 路由为 `rest`。
4. Memory 节点从 PostgreSQL 读取当前人物偏好和空间共享规则。
5. Experience 节点调用 DeepSeek，或在失败时生成规则降级结果。
6. Energy 节点计算舒适范围和节能建议。
7. Space Execution 节点根据 Adapter capability 生成动作与夜间步骤。
8. Harness 节点预检白名单、数值范围和空间规则。
9. Graph 输出 `Plan`，PostgreSQL 保存计划、trace 和 Outbox `plan.created`。
10. App 展示计划；此时设备没有变化。
11. 用户确认后，API 在 PostgreSQL 事务中幂等创建 Service。
12. Executor 每个动作前检查服务状态和版本，经 Adapter 写设备并回读。
13. 结果写入 PostgreSQL，并插入 `device.action.completed` Outbox。
14. Publisher 异步发送到事件总线；Consumer 更新活动投影和分析数据（活动记录本身在第 13 步已经同步写好）。
15. App 从同步响应看到当前结果，从活动接口看到后续事件轨迹。

## 9. 故障与降级策略

| 故障 | 预期行为 |
|---|---|
| DeepSeek 超时 | Graph 走规则 fallback；Plan 标明原因 |
| PostgreSQL 不可用 | 拒绝会改变事实的请求；不能假装执行成功 |
| Redis 不可用 | 回退到 PostgreSQL 锁与读取；记录告警 |
| 事件总线不可用（Kafka 停机或队列积压） | 主控制链路继续；活动记录照常同步写库；事件留在 Outbox 等待补发 |
| Consumer 重复收到事件 | `consumer_receipts.event_id` 去重 |
| 设备写入失败 | `ActionResult=failed`，服务不得误标完成 |
| 设备回读失败 | 标为“已发送但无法确认”，不自动盲目重试 |
| 用户停止 | 数据库先改变服务状态与版本；后续动作 guard 拦截 |
| API 重启 | PostgreSQL 恢复计划和服务；LangGraph 从 checkpoint 恢复规划状态 |

## 10. 建议实施顺序

不要同时改完所有基础设施。每一阶段必须保持现有演示可运行。

### 阶段 A：Docker 基线

状态：**已完成并通过宿主机验证**。2026-09-18 在用户Mac的Docker 29.6.2 / Compose 5.3.1上运行`./scripts/verify-t1.sh`成功：镜像构建、容器内默认模式测试（127通过 / 18跳过）、PostgreSQL迁移、Redis与API健康检查、非root用户、镜像无`.env`以及宿主机“计划 → 确认 → 回读 → 停止 → 重置”闭环全部通过。运行时只读挂载两个能源结果JSON，不把研究代码和模型权重放入容器。

- 为 FastAPI 添加 Dockerfile。
- T1 初始只容器化 `api`；T2–T5 完成后，Compose 再加入已被代码使用的 PostgreSQL、Redis、迁移和事件 Worker。
- 容器内运行现有后端测试（数量以 `docs/status.md` 为准，不在文档里写死）。
- Expo App 连接容器 API，完整闭环不变。

完成条件：新同学只需要 Docker Desktop、Node 和 Expo Go，即可启动后端。

端到端脚本（`apps/mobile/e2e/run_e2e.py`）默认仍启动本机 venv 后端，这条路径保持不变；容器路径作为另一条集成验证，不替换默认路径。

### 阶段 B：PostgreSQL 持久化

状态：**已完成（单实例）**。B1 基础设施与人物偏好、B2 计划 / 服务 / 整晚步骤 / 动作结果 / 活动记录都已落库，`LIVINGMIND_DATABASE_URL` 为空时行为与以前完全一致。整套测试可以换存储实现再跑一遍（`LIVINGMIND_TEST_STORE=sql`），在真实 PostgreSQL 16 上全部通过。并发由单进程锁、数据库约束和T4 Redis协调共同保证。Compose的`postgres`健康检查、一次性`migrate`以及迁移后API启动已在宿主机验证通过。

落地细节与本文 4.2.1 的对照：每空间一个 active 服务 = `services.active_space_id` 上的唯一索引；夜间步骤只执行一次 = `UPDATE scheduled_steps … WHERE status='pending' RETURNING`；进行中的工作 = `service_flags` 行；代次 = `space_state.epoch`，停止与重置只增不减。存储层对两种实现都返回**副本**，所以“改了不存”会在内存实现里同样失败，不会出现只在内存下侥幸正确的代码路径。

- 在 Compose 中加入 `postgres`，由健康检查约束 API 启动与迁移流程。
- 引入 SQLAlchemy 与 Alembic。
- 先迁移人物偏好、计划、服务、动作结果和活动记录。
- Repository 同时保留内存实现用于快速单元测试。
- 增加重启恢复和并发确认测试。

完成条件：后端重启后人物偏好、活动和已结束服务仍存在；同一计划不会重复执行。

### 阶段 C：LangGraph 规划图

状态：**已完成（规划分支）**。编排器拆成阶段方法，legacy 与 graph 两条路径调用同一批方法；图只负责路由、顺序和状态。`LIVINGMIND_ORCHESTRATOR=langgraph` 时整套测试再跑一遍全部通过，且与 PostgreSQL 存储组合也通过；`scripts/compare_orchestrators.py` 对 5 组输入比对等价。事件调整仍走 legacy 单阶段（包成图不增加可观察的步骤，已在代码注释与文档写明）。checkpoint 在配了数据库时由 `PostgresSaver` 自建表（`checkpoints` 等），与业务表分开。

- 用 Graph 节点包装现有类，不复制业务规则。
- 使用 PostgreSQL checkpointer。
- 保留 `LIVINGMIND_ORCHESTRATOR=legacy|langgraph` 开关做结果对照。
- 新增节点轨迹和 checkpoint 恢复测试。

完成条件：相同输入在 legacy / graph 模式产生等价 Plan；App 展示真实节点轨迹。

### 阶段 D：Redis 协调

状态：**已完成（空间锁 + 冷却快速判断）**。锁带随机 token 与 30 秒 TTL，只删自己的锁；Redis 未配置或连不上时锁自动退化为无操作，流程照走数据库路径。第二个实例在空间被驱动时收到 `SPACE_BUSY`。未做：设备状态缓存（当前设备读取就在内存里，缓存只会带来过期风险）、幂等结果缓存（数据库层已经幂等）。

- 加入冷却、短期幂等缓存和空间锁。
- PostgreSQL 约束仍为最终防线。
- 增加 Redis 断开时的降级测试。

完成条件：多 API 实例下同一空间仍只有一个 active service；Redis 停止后核心流程仍可运行。

### 阶段 E：Outbox 与事件总线（Kafka 可选）

状态：**已完成（数据库队列实现）**。业务事实与 outbox 行在同一事务提交；publisher 用 `FOR UPDATE SKIP LOCKED` 领取、失败退避重试、超过次数进入死信但不删除；consumer（activity-projector）用 `consumer_receipts` 去重并投影到 `service_projection`。App 显示的活动记录仍由 API 同步写库，不依赖投影。**Kafka 实现故意没写**：目前没有 broker 可验证，仓库里放一个未验证的发布器比不放更糟；接口是 `EventPublisher`，将来补一个实现即可（message key = spaceId）。

- 建 `outbox_events`、`consumer_receipts` migration。
- 实现 `EventPublisher` 协议 + 数据库队列实现 + Outbox Publisher + 一个真实 Consumer：`activity-projector`。
- 所有消息携带 `event_id`、`correlation_id` 和 `schema_version`；消费者按 `event_id` 去重。
- 测试：总线停摆、恢复补发、重复投递、Consumer 重启、同一空间保序。
- Kafka 实现与 `kafka` profile 作为可选项；跑通一次即留证据，平时保持关闭。

完成条件：总线停摆期间设备仍能执行；恢复后待发送事件补发；重复消息不产生重复活动；活动记录始终由同步写入保证。

### 阶段 F：集成与演示冻结

状态：**工程化集成冻结已完成**。Compose 全栈启动及两个 Worker 实际运行通过；Outbox 7/7 发布消费，Worker 重启后无重复；Alembic 0001→0003 与 0003→0002→0003 通过；三套后端组合分别为 127/141/145 项通过；Docker API 浏览器端到端 20/20。GitHub Actions 运行 `35333253707` 的 6 个 Job 全部通过（T6 冻结当时；此后 E 专项的 `35409969801` 同样 6/6 全绿）。证据表已重新生成并检查。**尚未完成的是平板真机验收**，需要物理设备。

- Compose 一键启动全部后端服务。
- GitHub CI 增加 migration、容器健康和集成测试：PostgreSQL 与 Redis 用 service containers 起；Kafka 相关测试单独一个可选 job 或只在本地跑。
- Playwright 与真机重新跑完整闭环。
- 更新证据表，只有真实运行过的能力才写“已实现”。

### 受控执行专项：Agent 没有设备权限

状态：**虚拟设备主路径已实现并验证**；真实 SpaceMind / 厂商对端待接入。

```text
Plan
  → PolicyDecision（规则结果 + 语义哈希 + require_confirmation）
  → 用户确认
  → ExecutionGrant（人物/空间/计划/版本/哈希/服务/代次/能力/时间上限）
  → Executor（服务 guard + 平台策略 + grant 缩权）
  → ActionExecution（持久化状态转移）
  → DeviceGateway（actionId 幂等 + serviceEpoch fencing）
  → receipt + readback
```

关键语义：

1. 授权只在确认时产生，只能缩小平台与设备能力的交集，不能赋予超出 Harness 的能力。一次性设备指令还会把范围锁定到用户确认的具体数值；持续服务只保留已确认场景中出现的设备/命令对。
2. 停止、服务完成或失败会撤销 grant；停止/重置同时提升空间代次，旧命令在 Gateway 写入前被拒绝。
3. Gateway 在离开锁写设备前先保留 `actionId`；并发重试看到 `accepted`，不会第二次写设备。同 ID 不同载荷直接拒绝。
4. `ActionExecution` 状态为 `pending / dispatching / accepted / completed / failed / rejected / unknown / cancelled`。已受理但终态不明时记为 `unknown`，启动恢复不自动重放。
5. 虚拟 Gateway 证明了契约和并发语义，不等于真实硬件已联调；真实接入必须在设备网关侧同样执行幂等与 fencing。

## 11. 验收测试清单

| 技术 | 必须证明的测试 |
|---|---|
| PostgreSQL | 重启后数据存在；事务回滚不留半个服务；并发确认只有一个成功；夜间步骤并发推进只执行一次；演示重置只清演示账户 |
| LangGraph | 条件分支正确；模型失败降级；checkpoint 可恢复；节点 trace 与实际一致；legacy / graph 双路径按 3.2 的等价定义比对通过 |
| Redis | 冷却 TTL；锁 token 校验；连接失败时数据库降级；不能因缓存旧值误报设备状态 |
| 事件总线 | Outbox 不丢；Publisher 重试；Consumer 幂等；同一空间事件顺序正确；总线停摆不影响活动记录 |
| Docker | 全新机器可构建；健康检查有效；Secret 不进入镜像；容器内测试通过 |
| 受控执行 | PolicyDecision / ExecutionGrant 绑定正确；grant 只能缩权；actionId 并发幂等；同 ID 异载荷拒绝；过期 epoch 拒绝；accepted 无终态转 unknown；设备回读不一致失败 |

## 12. 面试时如何解释

### 为什么同时用 PostgreSQL、Redis 和事件总线？

PostgreSQL 保存业务事实；Redis 加速短期状态和跨实例协调；事件总线把已发生的事件异步分发给审计、分析和未来主动服务。三者责任不同，任意一个都不应被当作另外两个的替代品。

### 为什么默认没有跑 Kafka？

当前只有一个后端进程和一个消费方，引入常驻中间件（约 1 GB 内存）解决不了任何现有问题。真正需要的是事务一致性与异步分发这套模式，它在 Outbox + 数据库队列里已经完整实现：至少一次投递、`event_id` 幂等、重试、死信、按空间保序、多实例 `SKIP LOCKED` 竞争消费。发布端是一个接口，换成 Kafka 只改一个实现类；需要时开 `kafka` profile 即可。

### 为什么不让事件总线直接控制灯光？

设备控制需要低延迟确认、停止优先和立即回读。Kafka 更适合异步事件传播，且消费者必须处理重复消息。核心控制使用同步 Executor，Kafka 只传播执行后的事实。

### 如何保证数据库更新与事件一致？

业务数据和 Outbox 行在同一个 PostgreSQL 事务中提交；独立 Publisher 再发送到总线。即使总线暂时不可用，事件仍保存在数据库中，不会静默丢失。

### Redis 锁是不是最终安全保证？

不是。Redis 锁用于减少竞争，PostgreSQL 唯一约束、行锁和版本号才是最终正确性保证；Redis 故障时系统应退回数据库路径。

### LangGraph 的价值是什么？

它把路由、Memory、Experience、Energy、Space Execution、Harness 表达为可观测的有状态图，并提供 checkpoint 和条件边；它不替代设备安全执行器。

### Memory 和 checkpoint 有什么区别？

人物 Memory 是产品数据，例如林悦偏好 25°C；checkpoint 是一次 Agent 工作流执行到了哪个节点。两者都可存 PostgreSQL，但生命周期、权限和数据模型不同。

## 13. 上手顺序

1. 从 `POST /api/assistant/messages` 跟一次“我想休息”。
2. 阅读 `Orchestrator → Planner → SpaceExecutionAgent → Harness`。
3. 理解 `Plan` 与 `Service` 的区别：计划先生成，确认后才执行。
4. 阅读 `MemoryService`，确认人物偏好和空间规则如何隔离。
5. 阅读 `harness/policy.py → grants.py → executor.py → adapters/gateway.py`，理解为什么模型和 LangGraph 都没有设备权限。
6. 完成阶段 B 后，本地查看 PostgreSQL 中的 plan、service、action 和 outbox 行。
7. 完成阶段 D 后，用 Redis CLI 查看 cooldown 和 lock 的 TTL。
8. 完成阶段 E 后，查看 `outbox_events` 的领取与投递过程；开启 `kafka` profile 时再用 consumer 看同样的 envelope。
9. 手动停止 Redis、事件总线、模型服务，验证降级路径。
10. 最后再研究扩容、多实例和真实设备 Adapter。

## 14. 官方资料

- [LangGraph reference](https://langchain-ai.github.io/langgraph/reference/)
- [LangGraph checkpoint savers](https://langchain-ai.github.io/langgraph/reference/checkpoints/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Redis asyncio client](https://redis.io/docs/latest/develop/clients/redis-py/async/)
- [Redis distributed locks](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/)
- [Apache Kafka quickstart](https://kafka.apache.org/quickstart/)
- [Apache Kafka delivery semantics](https://kafka.apache.org/40/design/design/)
- [Docker Compose](https://docs.docker.com/compose/)

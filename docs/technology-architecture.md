# LivingMind 技术架构与上手指南

更新：2026-09-18

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
                                             Executor
                                                 │
                                      Device Adapter Protocol
                                                 │
                                   虚拟设备 / SpaceMind / 厂商底座

PostgreSQL：业务事实、人物记忆、计划、服务、动作、Outbox、Graph checkpoint
Redis：短期锁、冷却、幂等加速、热点状态；不可作为唯一事实来源
Kafka：动作完成后的领域事件、审计投影、分析；不在设备控制关键路径
Docker Compose：在开发机和 CI 中统一启动 API、数据库、缓存、消息系统和 Worker
```

设计原则：

1. 模型只生成体验目标，不能直接控制设备。
2. LangGraph 负责理解和规划；`RestService + Harness + Executor` 负责确认、停止和执行安全。
3. PostgreSQL 是唯一事实来源（source of truth）。
4. Redis 丢失后系统应能降级运行，不能丢失人物偏好或服务事实。
5. Kafka 故障不能阻止“确认、停止、设备执行”；待发送事件保存在 PostgreSQL Outbox。
6. 所有消费者按 `event_id` 幂等，不能假设消息绝不会重复。
7. Expo 原生开发继续在 Mac 运行；Docker 主要承载后端和基础设施。

## 2. 当前实现与目标实现

| 能力 | 当前实现 | 目标实现 | 状态 |
|---|---|---|---|
| 移动端 | Expo / React Native / TypeScript | 保持；连接容器化 API | 已实现 |
| API | FastAPI + Pydantic | 保持；增加 lifespan 资源管理和基础设施健康检查 | 已实现，待扩展 |
| Agent 编排 | Python 同进程顺序调用 | LangGraph `StateGraph` 包装现有模块 | 计划 |
| Experience Agent | DeepSeek Provider；结构化输出；失败降级 | 作为 LangGraph 节点复用 | 已实现 |
| 人物记忆 | `MemoryService` 进程内字典 | PostgreSQL 持久化；按人物隔离 | 演示版已实现，持久化计划中 |
| 运行状态 | `MemoryStore` 进程内保存计划、服务和活动 | PostgreSQL Repository | 演示版已实现，持久化计划中 |
| 并发控制 | Python 锁、space epoch、集合标记 | PostgreSQL 约束 + 行锁；Redis 做快速协调 | 已实现单实例，分布式计划中 |
| 设备 | 有状态虚拟 Adapter | 保持 Protocol，增加真实厂商 Adapter | 虚拟设备已实现 |
| 能源 | 在线规则 + 离线固定日仿真 | 保持边界；事件进入 Kafka 分析流 | 已实现规则与只读展示 |
| 异步事件 | 进程内活动记录 | PostgreSQL Outbox → Kafka → Consumer Projection | 计划 |
| 容器化 | 无 | Dockerfile + Compose | 计划 |
| CI | pytest、TS、契约、Playwright | 增加容器集成测试和迁移检查 | 已实现基础版，待扩展 |

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

### 4.3 如何实现

建议使用：

- SQLAlchemy 2.x：ORM、事务、连接池。
- PostgreSQL driver：在实施时锁定与 Python 版本兼容的驱动。
- Alembic：数据库结构迁移，每个 schema 变化必须有 migration。
- Repository Protocol：业务服务不直接写 ORM，方便测试时替换成内存实现。

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

- 使用 `redis-py`，若后端转为异步路由则使用 `redis.asyncio`。
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

## 6. Kafka：领域事件与异步处理

### 6.1 为什么需要 Kafka

Kafka 用于把“已经发生的事实”发送给不应阻塞主请求的下游：

- 审计与活动流投影。
- Agent / 模型耗时分析。
- 能源统计与演示数据汇总。
- 未来通知、主动服务触发器和设备遥测消费。

Kafka 不用于同步发送“现在关灯”的核心命令。确认、停止、执行和回读必须通过当前同步控制链路返回明确结果。

### 6.2 Topic 设计

首版只建少量稳定 Topic：

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

Kafka message key 使用 `spaceId`，保证同一空间事件进入同一分区并保持顺序。

### 6.3 Transactional Outbox

不能先写 PostgreSQL、再直接调用 Kafka；如果进程在两步之间崩溃，会出现数据库成功但事件丢失。采用 Transactional Outbox：

```text
业务事务：更新 service + 插入 outbox_events
                         ↓
Outbox Publisher：读取未发送行 → Kafka publish → 标记 published_at
                         ↓
Consumer：按 event_id 幂等处理 → 写 consumer_receipts
```

Publisher 使用 `FOR UPDATE SKIP LOCKED` 领取任务，可运行多个实例。Kafka 默认按至少一次思路设计消费者，因此重复消息是正常情况；消费者必须使用 `event_id` 去重。

建议目录：

```text
backend/app/events/
├── envelope.py
├── outbox.py
├── producer.py
└── topics.py
backend/workers/
├── outbox_publisher.py
├── activity_projector.py
└── energy_analytics.py
```

Kafka 不可用时：

- API、停止和设备控制继续工作。
- Outbox 行保持 `pending`。
- Publisher 指数退避重试。
- 超过重试阈值后写告警，但不删除事件。
- 恢复后补发；消费者幂等处理。

## 7. Docker Compose：可复现运行环境

### 7.1 服务组成

```text
services:
  api                 FastAPI + LangGraph + 业务服务
  postgres            业务数据 + LangGraph checkpoint
  redis               缓存、锁、冷却
  kafka               KRaft 单节点开发环境
  kafka-init          创建 Topic 后退出
  outbox-worker       PostgreSQL Outbox → Kafka
  activity-projector  Kafka → 活动流投影
```

Expo Metro、iOS 模拟器和真机调试继续在 Mac 上运行，不进入 Linux 容器。App 通过 `http://<Mac 局域网 IP>:8000` 访问映射出来的 API。

建议新增：

```text
compose.yaml
.dockerignore
backend/Dockerfile
backend/Dockerfile.worker
```

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
14. Publisher 异步发送 Kafka；Consumer 更新活动投影和分析数据。
15. App 从同步响应看到当前结果，从活动接口看到后续事件轨迹。

## 9. 故障与降级策略

| 故障 | 预期行为 |
|---|---|
| DeepSeek 超时 | Graph 走规则 fallback；Plan 标明原因 |
| PostgreSQL 不可用 | 拒绝会改变事实的请求；不能假装执行成功 |
| Redis 不可用 | 回退到 PostgreSQL 锁与读取；记录告警 |
| Kafka 不可用 | 主控制链路继续；事件留在 Outbox 等待补发 |
| Consumer 重复收到事件 | `consumer_receipts.event_id` 去重 |
| 设备写入失败 | `ActionResult=failed`，服务不得误标完成 |
| 设备回读失败 | 标为“已发送但无法确认”，不自动盲目重试 |
| 用户停止 | 数据库先改变服务状态与版本；后续动作 guard 拦截 |
| API 重启 | PostgreSQL 恢复计划和服务；LangGraph 从 checkpoint 恢复规划状态 |

## 10. 建议实施顺序

不要同时改完所有基础设施。每一阶段必须保持现有演示可运行。

### 阶段 A：Docker 基线

- 为 FastAPI 添加 Dockerfile。
- Compose 先只启动 `api`，不放入尚未被代码使用的装饰性基础设施。
- 容器内运行现有 115 项测试。
- Expo App 连接容器 API，完整闭环不变。

完成条件：新同学只需要 Docker Desktop、Node 和 Expo Go，即可启动后端。

### 阶段 B：PostgreSQL 持久化

- 在 Compose 中加入 `postgres`，由健康检查约束 API 启动与迁移流程。
- 引入 SQLAlchemy 与 Alembic。
- 先迁移人物偏好、计划、服务、动作结果和活动记录。
- Repository 同时保留内存实现用于快速单元测试。
- 增加重启恢复和并发确认测试。

完成条件：后端重启后人物偏好、活动和已结束服务仍存在；同一计划不会重复执行。

### 阶段 C：LangGraph 规划图

- 用 Graph 节点包装现有类，不复制业务规则。
- 使用 PostgreSQL checkpointer。
- 保留 `LIVINGMIND_ORCHESTRATOR=legacy|langgraph` 开关做结果对照。
- 新增节点轨迹和 checkpoint 恢复测试。

完成条件：相同输入在 legacy / graph 模式产生等价 Plan；App 展示真实节点轨迹。

### 阶段 D：Redis 协调

- 加入冷却、短期幂等缓存和空间锁。
- PostgreSQL 约束仍为最终防线。
- 增加 Redis 断开时的降级测试。

完成条件：多 API 实例下同一空间仍只有一个 active service；Redis 停止后核心流程仍可运行。

### 阶段 E：Kafka + Outbox

- 建 `outbox_events` migration。
- 实现 Publisher 和一个真实 Consumer：`activity-projector`。
- 所有消息携带 `event_id`、`correlation_id` 和 `schema_version`。
- 测试 Kafka 停机、恢复、重复投递和 Consumer 重启。

完成条件：Kafka 停止期间设备仍能执行；恢复后待发送事件补发；重复消息不产生重复活动。

### 阶段 F：集成与演示冻结

- Compose 一键启动全部后端服务。
- GitHub CI 增加 migration、容器健康和集成测试。
- Playwright 与真机重新跑完整闭环。
- 更新证据表，只有真实运行过的能力才写“已实现”。

## 11. 验收测试清单

| 技术 | 必须证明的测试 |
|---|---|
| PostgreSQL | 重启后数据存在；事务回滚不留半个服务；并发确认只有一个成功 |
| LangGraph | 条件分支正确；模型失败降级；checkpoint 可恢复；节点 trace 与实际一致 |
| Redis | 冷却 TTL；锁 token 校验；连接失败时数据库降级；不能因缓存旧值误报设备状态 |
| Kafka | Outbox 不丢；Publisher 重试；Consumer 幂等；同一空间事件顺序正确 |
| Docker | 全新机器可构建；健康检查有效；Secret 不进入镜像；容器内测试通过 |
| Executor | 白名单、范围、停止优先、重复确认、设备回读、部分失败 |

## 12. 面试时如何解释

### 为什么同时用 PostgreSQL、Redis 和 Kafka？

PostgreSQL 保存业务事实；Redis 加速短期状态和跨实例协调；Kafka 把已发生的事件异步分发给审计、分析和未来主动服务。三者责任不同，任意一个都不应被当作另外两个的替代品。

### 为什么不让 Kafka 直接控制灯光？

设备控制需要低延迟确认、停止优先和立即回读。Kafka 更适合异步事件传播，且消费者必须处理重复消息。核心控制使用同步 Executor，Kafka 只传播执行后的事实。

### 如何保证数据库更新与 Kafka 事件一致？

业务数据和 Outbox 行在同一个 PostgreSQL 事务中提交；独立 Publisher 再发送 Kafka。即使 Kafka 暂时不可用，事件仍保存在数据库中，不会静默丢失。

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
5. 阅读 `Executor`，理解为什么模型不能直接操作设备。
6. 完成阶段 B 后，本地查看 PostgreSQL 中的 plan、service、action 和 outbox 行。
7. 完成阶段 D 后，用 Redis CLI 查看 cooldown 和 lock 的 TTL。
8. 完成阶段 E 后，用 Kafka consumer 查看领域事件 envelope。
9. 手动停止 Redis、Kafka、模型服务，验证降级路径。
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

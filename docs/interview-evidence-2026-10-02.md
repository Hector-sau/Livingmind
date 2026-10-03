# LivingMind 面试证据基线

更新：2026-10-03（模型评测保留 2026-10-02 原始记录）。此表按可核对的代码、测试与原始结果整理；个人贡献待团队成员逐项确认。

语义保护与 40 次连接实验已发布为 `d3d0d87`。后续独立网关与双 API 最终代码为 **a3594c1**，CI [37114091256](https://github.com/Hector-sau/Livingmind/actions/runs/37114091256) 六项通过。设计与故障边界见 [独立网关说明](durable-gateway.md)，后续状态见 [交接](../AGENT-HANDOFF.md)。

| 主张 | 当前证据 | 边界 |
|---|---|---|
| 受控设备执行 | `backend/app/harness/`、`backend/app/adapters/gateway.py`、`backend/tests/test_execution_authority.py` | 已在虚拟网关验证；真实厂商网关尚未接入 |
| 真实模型选型 | `docs/evidence/model-latency-{chat,flash-2000}-{1,2}.json`：各 48 次；chat 48/48 被采纳、成功调用 P95 1450 ms；flash 46/48 被采纳、成功调用 P95 3539 ms | 5 条重复话术、4 个人设；P95 不含超时；59.0% 是历史观察，非端到端性能 |
| PostgreSQL 业务约束 | `backend/app/repositories/sql_store.py`、`backend/tests/test_persistence.py` | 数据库约束不替代真实设备幂等与多实例联调 |
| Redis 协调 | `backend/app/cache/locks.py`、`backend/app/cache/cooldown.py`、`backend/tests/test_cache_coordination.py` | 短锁和冷却；未做数据缓存提速实验；锁无续租 |
| 事务出箱 | `backend/app/events/outbox.py`、`backend/tests/test_outbox_events.py`；独立数据库连接并发写入、发布、消费已验证 | PostgreSQL 事件队列；按空间保序；未接 Kafka，未做长期生产压力测试 |
| 自动化回归（最终代码） | CI 默认 **210/42**、SQL+legacy **242/10**、全栈 **251/1**；前端 **101**、类型/契约；Docker 浏览器 **28/28**；本机 iOS/Android JS 导出通过 | `github-ci-37114091256.json`、`durable-gateway-browser-2026-10-03.json`；导出不是安装包/真机，中间版本 XML 不与最终数量混算 |
| 请求语义保护 | 12 条新增开发回归；前端 Mock 和浏览器澄清流程同步 | 明确否定/限制先澄清；只检查列出的方向模式，不是通用语言理解。旧 v2 的失败已用于开发，新 v3 30 条候选待人工审核 |
| 连接复用实验 | deepseek-flash 真实 40 次：每组 20 次；P50 1529.759→1393.337 ms，P95 2642.971→2972.948 ms，均通过预置方向检查 | `real-http-pooling-2026-10-03.json`；本地 HTTP API+内存存储，不含平板/设备；**P95 未改善，默认不启用**。不与模型选型的 96 次混算 |
| 未知动作回执核对 | 15 条专项用例；只 query 不 submit；账本/计划/单次活动记录同事务；App 已有核对按钮 | `tests/test_action_reconciliation.py`；独立网关回执持久化，原单实例模式仍在内存；停止后不续跑；直接控制核对入口仍有限 |
| 双 API 故障验证 | 真实 HTTP 进程，覆盖跨实例停止、重复/不同计划、Redis TTL/断连、API/网关重启、共享撤销和首次重置 | `test_http_replicas.py` **9 场景**、`test_persistent_gateway.py` **10 用例**；最终全栈 CI 均通过，非物理设备或生产可用性保证 |
| 依赖修补 | xcode 使用的 uuid 升级至 11.1.1；受影响包 23→16，根公告 3→2 | `dependency-risk.md`、修补后原始审计；剩余 16 high，没有宣称全修复 |

## 2026-10-02 至首次 10-03 发布的历史实验

| 实验 | 实测结果 | 原始记录与边界 |
|---|---|---|
| 独立路由验收 | 30 条预设标签的模拟请求，29/30；遗漏 `h26`（空调开关歧义被误判成设备指令） | `backend/evals/holdout_v2.json`、`docs/evidence/holdout-v2-route-2026-10-02.json`。AI 编制，尚未独立人工审核；没有用于本轮两处路由修复，与开发回归集分开；不能称真实用户准确率 |
| 配对模型对照 | 相同 12 条休息请求交错调用：chat 11/12 通过方向性语义检查、0 降级、P95 1452 ms；flash 9/12 通过、3 次超时降级、P95 6272 ms | `docs/evidence/holdout-v2-model-paired-2026-10-02.json`。按预置期望检查灯光/温度/窗帘相对偏好的方向，不是专家对完整语言理解的评分。统一提示词、6 秒超时、2000 输出预算、温度 0.3；每模型仅 12 次，nearest-rank P95 此时接近最大值；计时为服务层创建计划，不含 HTTP、确认与设备动作。chat 保留 1 条错误 |
| 用量记录 | chat 12/12 返回 Token 用量，共 6291；flash 9/12 有用量，共 7138，3 次超时无用量回执 | 同一原始结果；不能据此比较完整费用，超时调用仍可能计费，且未锁定价格 |
| 跨进程并发与崩溃 | 两个 OS 进程运行服务层，共用 PostgreSQL、Redis 和独立虚拟网关：同计划并发确认只产生 3 次设备写入；另一进程停止后，已在途写入可完成，剩余动作不执行；迟到旧代次命令被拒绝。执行中杀死服务进程后，重启把结果未知动作标记为 `unknown`，租约过期后重复确认也不重放 | `backend/tests/test_multiprocess_gateway.py` 是服务层测试夹具，并非两个真实 HTTP 副本。当前 Compose 虚拟设备仍在 API 进程内，**不能直接扩成两个生产 API 副本**；两个测试进程须在接收请求前完成启动恢复，生产扩容还需要独立网关及按实例所有权恢复 |
| Redis 故障注入 | 首个设备写入阻塞期间，使 1 秒测试租约过期或切断 Redis TCP 代理连接；第二个进程重复确认同一计划，没有新增写入；放行后总计仍只有 3 次设备写入 | 同上两个参数化测试。证明这条重复确认路径在协调失效时的行为；不代表所有不同计划、真实设备或网络分区都已验证，也未实现锁续租 |
| 网关回执丢失 | 提交前断连、写入后回执超时、查询回执超时三种注入，均持久化为 `unknown`；重复确认不重发 | `backend/tests/test_execution_authority.py`。修改前 3 条用例均因异常抛出而失败，修改后通过；设备状态究竟是否改变取决于丢失发生的位置，不能把超时说成“肯定没执行” |
| 前端如实呈现结果 | unknown 显示“执行结果待确认”，失败显示“未确认完成”，只有非空且全成功的结果才显示绿色完成；4 条纯逻辑测试及 1 条浏览器场景通过 | `features/chat/conversation.ts`、`MessageView.tsx`、`tests/conversation.test.ts`；浏览器 `http-unknown-receipt` 只注入未知回执响应，不能当作真实设备断网证据 |
| Outbox 顺序与恢复 | 同空间两个写入事务按顺序提交；两个 publisher 和两个 consumer 都不能越过被锁住的早期事件；投递后崩溃重试不重复入队；死信显式重投；迟到 started 不使 stopped 投影复活 | `backend/alembic/versions/0006_outbox_order.py`、`backend/tests/test_outbox_events.py`。死信阻塞该空间后续事件，需人工处理；并非全局严格排序 |
| 本地链路基线 | 加入分段日志后，30 次内存规则模式 TestClient：计划 P50/P95 1/1 ms，确认 P50/P95 2/3 ms | `docs/evidence/rule-path-observed-2026-10-03.json`；较早记录保留在 `rule-path-local-2026-10-02.json`。毫秒取整、进程内虚拟设备；只作烟雾基线，不用于真实网络性能或提速声明 |

本轮本地与 GitHub 三套后端结果一致：内存 170 通过、33 跳过；PostgreSQL + legacy 195/8；PostgreSQL + Redis + LangGraph 202/1。前端类型检查与 92 项测试通过，契约重新生成无 diff。最终 UI 的本地内存浏览器 28/28；[GitHub CI 37038661216](https://github.com/Hector-sau/Livingmind/actions/runs/37038661216) 对 `7867d9c` 的 Docker 浏览器也 28/28，六项 Job 全部通过。CI 浏览器使用 Compose 默认 legacy 编排，LangGraph 由独立后端 Job 覆盖；模型使用本地桩。本机最终容器复测仍受 Docker 内部存储启动问题阻断，不能称本机 Docker 已修复。0006→0005→0006 本地迁移与 CI 的 head→0002→head 均通过。先前本机 27 场景 E2E 末尾队列 pending=0、dead_letters=0，投递事件/消费回执均为74（历史验收快照，非吞吐统计）。真机及真实硬件未验。

暂停前失败的根因已查明：崩溃后的进程不能主动释放 Redis 租约，立即重试被 `SPACE_BUSY` 拒绝是正确行为。测试现在先核对租约存续时的拒绝，再等短测试租约过期并验证不重放。另一个日志问题来自 Alembic `fileConfig` 默认关闭已有日志器；已通过 `disable_existing_loggers=False` 修复，并使用真实日志 Handler 验证输出，而不是只 spy 方法调用。

## 日志怎样帮助解释一次请求

`X-Request-ID` 同时进入 HTTP 日志与事件 `correlationId`；`agent.stage` 记录路由、记忆、Experience、Energy、动作规划与 Harness 耗时；`plan.ready` 连接到 planId/actionIds；确认请求产生 `action.finished`（planId/serviceId/actionId、耗时、结果）和 `gateway.write` / `gateway.readback` 分段记录。日志不记录用户话术、模型提示词、密钥或人物偏好值。外部网关进程须通过 actionId 继续关联，不能假定 Python contextvar 会自动跨进程传递。

## 复现入口与读数方法

`backend/.venv` 若仍为旧 Python 3.9 环境，不要继续在里面安装依赖；使用 Python 3.11/3.12 的新虚拟环境和仓库 `constraints.txt`。在 `backend/` 下：

```bash
python scripts/evaluate_holdout.py --dataset evals/router_challenge_v1.json
python scripts/evaluate_holdout.py --dataset evals/holdout_v2.json
python scripts/path_baseline.py --rounds 30
# 下面两项调用真实 DeepSeek，会产生费用；先在本地配置密钥，不要提交密钥：
python scripts/evaluate_holdout.py --dataset evals/holdout_v2.json --model
python scripts/compare_models.py --models deepseek-chat deepseek-flash
```

阅读原始 JSON 时分清 `route.correct/total`、`semantic.pass/fail/fallback` 和 `usage_reported_count`。模型 P95 包含超时后的降级耗时，不包含 HTTP App 往返、用户确认或设备动作；本地规则链路是独立指标，不能与模型耗时相减算“提速”。修改提示词或路由后，v2 就不再是未接触的验收集，应冻结旧结果并建立下一版本。

## 待补实验（按当前状态更新）

1. `h26` 歧义已修复为澄清。v2 已进入历史/回归角色；审核并冻结 v3 候选标签后，才能获得新的未调参验收结果。
2. 当前已补只读回执核对，尚需独立持久化网关、按所有权启动恢复和两个真实 API 实例。再验证不同计划竞争、网关自身重启和所有写入路径；不要把已有的服务层多进程夹具当成部署验收。
3. 对 Outbox 做更长时间的并发压力试验与跨空间公平性检查；保留死信人工处理的运维说明。
4. 在真实平板、真实网络和至少一种真实设备上建立端到端延迟与回读基线；本地毫秒数字不可外推。

## 个人贡献（待本人确认）

简历只写本人能说明设计、实现和验证过程的部分；团队总代码与测试数量不能直接推定为个人成果。

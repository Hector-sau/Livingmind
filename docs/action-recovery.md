# 设备操作记录与后台结果核对

Updated 2026-10-03. Every device entry point now has an action record. Recovery queries existing receipts; it never resends a command or resumes a stopped service.

更新于 2026-10-03。本文帮助接手同学理解这一批设计：休息计划、手动控制、撤销都记录动作；后台只查询原回执，不重新执行。最新测试数字和发布状态以交接文档顶部为准。

## 为什么补这一步

以前计划动作可以核对，但手动控制和撤销只有网关回执，缺少完整的业务动作记录；API 崩溃后的扫描只在启动时运行。现在让三个入口共用记录与核对语义，并用独立 Worker 处理遗留动作。没有新增 Agent，也没有引入新的消息中间件。

## 动作记录怎样统一

- Executor 在发送前写入 `pending`、再写 `dispatching`，记录人物、账户、空间、目标、来源和 `actionId`。数据库写失败时不能先发设备指令。
- 计划继续使用有界 `ExecutionGrant`；低风险手动操作仍由服务端校验上下文、执行白名单/范围/代次检查，不伪造一个休息计划。手动动作的 `planId/grantId` 为 null，`source` 为 manual 或 undo。
- 撤销是一条新动作，带自己的 `actionId`。撤销窗口在发送前消费；新控制也会使旧撤销失效，避免回复未知时回滚另一条动作。
- 回读快照失败仍返回已知动作结果，`deviceState=null` 并警告。动作完成不代表之后还能读取设备，也不代表设备一直保持该值。
- `GET /api/actions` 返回经过账户/人物/空间检查的最近记录，当前扫描空间最近 200 条并返回本人物最多 50 条，不是无限历史查询。
- `POST /api/actions/{id}/reconcile` 只查原回执。计划、手动和撤销均支持；终态与一次核对活动记录在同一事务提交。迟到的 unknown 不能覆盖终态。

## 后台如何收尾

`app.services.recovery_worker` 是独立进程，只在 PostgreSQL + 持久化 HTTP 网关模式运行。进程内虚拟设备不能由另一个进程代查，因此原默认演示不启动它。

1. 扫描失去执行所有者的工作，复用 SQL 会话锁检查；有主的长任务不会仅因为耗时久就被接管。旧模式没有 ownerId 的行不由常驻 Worker 回收。
2. 对 unknown 动作使用 `FOR UPDATE SKIP LOCKED` 短事务认领，保存随机 token 与租期，再提交事务。
3. 事务外查询网关，不持有行锁等待 HTTP。成功时按 token 与当前状态核对，再更新业务记录。
4. 没有可靠回执就保留 unknown，按 2、4、8…秒退避，单次间隔最多 60 秒。默认最多 5 次自动认领、从请求起最多 15 分钟；租期至少 30 秒，并给网关超时留出余量。
5. 超限显示“自动核对已暂停”，不当作执行失败。用户仍可手动核对；这不是自动重试指令。

认领后 Worker 崩溃可能消耗一次尝试，即使 HTTP 尚未发出，所以 `recoveryAttempts` 是自动认领/尝试数，不冒充成功查询次数。租期过期允许另一个 Worker 再查，旧 token 不能覆盖新认领结果。重复的只读查询可以容忍；重复的设备写入不允许由恢复模块发起。

数据库不可达时，本轮恢复停止；不能跳过数据库直接去控制设备。停止与核对互不等价：补齐某条历史动作结果，不恢复服务、不继续剩余步骤。重置删除动作后，迟到的核对不能创建回记录。

数据库断连已增加真实 TCP 故障验证：认领前、收到回执后、结果提交后断连，以及后台进程在断连后继续存活。详细实验、失败记录和边界见 [数据库断连验证](database-fault-validation.md)，这仍不是所有网络分区场景或生产高可用证明。

## 页面怎样表达

空间页新增“操作记录与结果核对”，不依赖技术证据开关。显示来源、设备、目标、状态、自动尝试次数、上次及下次核对时间。用户刷新列表看到后台最新状态，也可以点“核对原动作（不重发）”。页面不会自动修改设备读数来冒充刚刚发生的新回读。

切人物或离开页面后，迟到请求不会给另一个人物补入记录。前端 Mock 明确说明没有持久化回执，不模拟一个成功恢复。网页 E2E 的未知展示使用响应注入；真正的丢回复、崩溃由后端进程测试制造，两种证据不可混说。

## 运行与代码入口

使用已有 `compose.gateway.yaml`，现在会同时启动 recovery 服务。网关 token 仍从本机环境读取，不写进 Git。

```bash
docker compose -f compose.yaml -f compose.gateway.yaml --profile replicas up -d --build
docker compose -f compose.yaml -f compose.gateway.yaml logs recovery
```

| 模块 | 入口 |
|---|---|
| 统一动作记录 | `backend/app/harness/executor.py`、`contracts/models.py` |
| 手动与撤销 | `backend/app/services/rest_service.py` |
| SQL 核对认领与退避 | `backend/app/repositories/action_recovery.py` |
| 后台循环与查询 | `backend/app/services/recovery_worker.py` |
| 回执证据判断 | `backend/app/harness/reconciliation.py` |
| 人物隔离列表与按钮 | `apps/mobile/features/activity/ActionHistory.tsx` |
| 两 API 与独立 Worker 实验 | `backend/tests/test_http_replicas.py` |
| 退避、租期、停止、重置测试 | `backend/tests/test_background_recovery.py` |

数据库迁移为 `0008`。升级保留旧计划动作；回退到 `0007` 会失去新字段，且旧版本无法表达无计划的手动动作。因此存在此类记录时，迁移明确拒绝回退，不偷偷删除或伪造数据。需先停相关进程、备份，再另行决定证据归档与回退方案；不要在有用数据上运行测试回退。

## 亲自验证的三个问题

先写自己的预测，再跑对应测试，最后阅读日志和断言：

1. 调灯成功但回复丢失，再核对会不会重新调灯？看 `test_control_and_undo_lost_replies_can_be_reconciled_without_writing`。
2. API A 崩溃，API B 不重启，谁来收尾？看 `test_running_worker_recovers_crashed_api_without_restarting_surviving_api`。
3. 用户已经停止，迟到的回执会不会恢复服务？看 `test_background_receipt_after_stop_does_not_resume_service`。

测试只指向 `livingmind-eval` 专用 PostgreSQL 和 Redis DB 15，不能使用演示保留数据或其他项目数据库。

## 尚未证明的内容

这不是生产高可用或真实设备 exactly-once。SQL 与网关仍是单节点，网络分区检测有时延，存活但卡住的 API 不等于死亡所有者；当前没有自动接管其执行权。恢复 Worker 不是夜间定时调度器，也不自动继续未执行的控制。正式登录授权、真实设备协议、iPad/安卓安装与现场体验仍需独立验收。

手动控制 API 目前由服务端生成动作 ID；客户端重新提交控制请求会被视为一次新操作，不承诺任意客户端重发都幂等。本批次保证的是恢复流程和核对页面不会重发设备命令，而不是增加了所有入口的客户端幂等键。

新 30 条 Agent 评测必须先人工审核。审核过程见 [评测集审核](evaluation-review.md)，不能把本批次工程测试数量换成 Agent 准确率。

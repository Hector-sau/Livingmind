# 数据库断连时如何保护设备动作

The recovery worker now has tests using real database connection failures. They strengthen the evidence for the existing design; they do not add a new business feature or prove production high availability.

这轮补的是工程验证，不是新增产品功能。此前数据库不可用主要靠抛异常模拟；现在通过本地 TCP 代理真正关闭恢复进程的数据库连接，并验证恢复后的动作记录、活动记录和虚拟设备状态。业务实现没有因此改写。

## 解决的问题

设备已经执行，但业务系统还没记下结果时，数据库再断开，系统最容易做错两件事：把“没保存成功”当成“设备没执行”，或者收到回执后过早宣称业务记录已更新。

LivingMind 的处理方式是：数据库负责事实和恢复租约，网关保存动作回执。恢复流程只查询原 actionId，不重新提交控制命令。数据库暂时不可达就结束本轮检查，下一轮继续；没有成功落库的结果仍然是 unknown。

## 四个实际实验

| 断连位置 | 注入方法 | 验证结果 |
|---|---|---|
| 认领任务前 | 切断已有连接，并拒绝新连接 | 真实 SQL 驱动报错；没有查询网关，没有增加认领次数；连接恢复后同一个 Worker 对象完成核对 |
| 已读到完成回执，但还没写入数据库 | 实际 HTTP 查询回执成功后关闭数据库代理连接 | 账本仍 unknown，原租约保留；恢复连接后不能抢占未到期租约；测试时钟推进后重新查询，最终只产生一条核对活动 |
| 结果已经提交，但收尾数据库操作前 | 真实 SQL 事务返回后关闭连接 | 后续报错不会把 completed 降回 unknown；再跑一轮不重新查询该终态动作，也不追加活动 |
| 独立后台进程运行期间 | 断连状态启动真实 recovery 子进程，看到 OperationalError 日志后恢复连接 | 原 PID 保持存活，无需重启；连接恢复后完成待核对记录，日志不包含测试 token 或数据库 URL |

四项实验中，虚拟网关的设备版本都保持 1，只有最初那次控制写入。前三项还把 submit 替换成一旦调用就失败的断言，确认恢复只调用 query。第四项观察独立进程与持久化虚拟设备，没有声称验证了真实硬件。

断连后的两次查询是**只读查询重试**，不是设备动作重试。认领后未能保存结果，自动尝试数会被消耗；这符合当前设计，不能把次数解释为成功查询次数。

## 测试如何搭建

- PostgreSQL 使用独立的 livingmind-eval 项目；不停止数据库服务，也不影响其他项目。
- 测试代理仅转发本地 PostgreSQL 流量。cut 关闭已建立的 socket，并拒绝新连接；heal 允许重新连接。它不是静默丢包、数据库主从切换或整机宕机。
- 恢复路径启用 SQLAlchemy 连接池与 pool_pre_ping，覆盖已有连接被切断后的重新建立。
- 测试观察使用另一个直连连接，故障期间仍能检查数据库原值，但不会替恢复 Worker 绕过代理。
- 网关是独立 HTTP 进程，设备状态与回执保存在测试 SQLite 文件中。

代码入口是 `backend/tests/test_recovery_database_faults.py` 与 `backend/tests/tcp_fault_proxy.py`；被验证的业务实现仍为 `app/services/recovery_worker.py`、`repositories/action_recovery.py` 和 `repositories/sql_store.py`。

首次组合测试发现了一个**新增测试夹具的清理错误**：monkeypatch 的回滚顺序把 SQL 配置留给后续测试，导致旧记录影响断言。现已让夹具显式恢复自己的配置，再交给外层 SQL 夹具清理；没有放宽断言。失败记录保留在 `evidence/recovery-db-faults-fixture-failure-2026-10-03.xml`，修正后 34 条相关测试通过，见 `evidence/recovery-db-faults-final-2026-10-03.xml`。这不是产品曾重复执行设备的证据。

## 自己动手验证

先回答三个问题，再看测试断言：

1. 已收到完成回执，为什么数据库里仍可能显示 unknown？
2. 网络恢复了，为什么不能马上抢走尚未过期的租约？
3. 数据库已提交后出现异常，为什么下一轮不能再创建一条完成记录？

在专用测试数据库已启动、依赖已安装的情况下，从 backend 目录运行。下面地址只用于本项目测试库；测试会清空测试表，不能改成真实或需要保留的数据地址。

```bash
LIVINGMIND_TEST_DATABASE_URL=postgresql+psycopg://livingmind:livingmind@127.0.0.1:55432/livingmind \
python -m pytest tests/test_recovery_database_faults.py -v -p no:cacheprovider
```

## 能讲什么和不能讲什么

可以讲：“我用真实 TCP 断连验证恢复流程，在认领、回执读取、数据库提交几个边界检查行为。系统保持未知状态，恢复后只核对原回执，不盲目重放；已经提交的终态不会被后续异常覆盖。”个人是否负责该设计、实现或实验，仍需本人据实说明。

不能讲“数据库断网零影响”“物理设备 exactly-once”或“生产高可用”。尚未覆盖静默网络黑洞、数据库故障转移、API 正在执行时的所有数据库分区组合、长期负载以及真实厂商设备。此次也没有生成新的模型准确率、响应提速或费用指标。

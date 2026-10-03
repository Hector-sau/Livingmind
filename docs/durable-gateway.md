# 独立虚拟网关与双 API 验证

更新：2026-10-03。本文说明新实现解决了什么问题、怎样复现，以及它没有证明什么。当前发布和完整回归结果以 [交接文档](../AGENT-HANDOFF.md) 顶部为准。

**The API can restart without losing the virtual device's state or receipt. This is a tested simulation, not a real-device deployment.**

现在可以用两个独立 API 进程连接同一个持久化虚拟网关。API 重启不再等于设备状态重置；设备已经执行但回复丢失时，可以查询原动作的回执，不必重发。这一轮验证的是可重复的本地故障实验，不是生产负载或真实硬件验收。

## 原来有什么问题

旧版每个 API 进程各自保存虚拟设备和回执。直接启动第二个 API，会出现两份不同的灯光状态；重启后也可能找不到第一份回执。旧版启动恢复还会清理全部进行中的任务，无法区分“另一实例正在执行”与“上次崩溃留下的任务”。因此，不能仅靠 PostgreSQL、Redis 或 Docker 就说支持多实例。

## 现在怎样分工

```text
App
  → API A 或 API B
      → PostgreSQL：计划、服务、授权、动作账本、偏好、撤销窗口
      → Redis：可选短锁和冷却；不是设备数据缓存
      → HTTP 虚拟网关
          → SQLite：设备状态、actionId 回执、空间代次
```

三个数据来源没有混在一起。PostgreSQL 管理业务事实；网关管理“这条动作是否改变过虚拟设备”；Redis 失效不能成为重复写设备的理由。模拟设备和回执能在一个 SQLite 事务里提交，是因为设备本身就是数据。真实厂商设备不能参与这个事务，仍需厂商 actionId、回执查询与对账协议；本项目没有证明真实设备 exactly-once。

## 关键设计与代码入口

| 问题 | 当前做法 | 阅读入口 |
|---|---|---|
| 网关重启丢状态 | 独立进程和专用 SQLite 卷；状态、回执同事务提交 | `backend/app/adapters/persistent_gateway.py` |
| 同动作被重复发送 | actionId 唯一；相同命令返回原回执，改参数则拒绝；不会再次增加设备版本 | 同上、`test_persistent_gateway.py` |
| 停止后的旧命令迟到 | 网关持久化空间代次，拒绝旧代次的新动作；已经完成的动作仍返回原历史回执 | 同上 |
| 两个 API 同时写 | 共享网关模式持有 PostgreSQL 会话级空间锁；直接控制、撤销、确认、环境调整和时钟推进走同一边界 | `db/ownership.py`、`RestService._space_lock` |
| Redis TTL 过期或断网 | PostgreSQL 空间锁仍保护正在执行的批次；Redis 只辅助协调，没有伪装成缓存优化 | `test_http_replicas.py` 的两项协调失效实验 |
| 新 API 启动误取消旧 API | 每个进程持有专属 PostgreSQL 会话锁，运行中步骤和动作记 ownerId；仅恢复失去所有者的工作 | `SqlStore.startup_reconcile`、迁移 `0007` |
| 查询结果未知的动作 | App 的“核对结果（不重发）”只走 reconcile API；终态账本、计划结果和一次活动记录一起提交 | `harness/reconciliation.py`、`features/chat/` |
| 网关离线时用户停止 | 先保存停止和失效代次，再联系网关；联系失败时返回 stopped、空设备状态和明确 warning | `RestService.stop_service` |
| 多实例撤销与能源模式 | PostgreSQL 保存撤销窗口和能源模式；人物、代次、到期时间仍要校验；撤销先消费再发动作 | `shared_settings`、`control_device`、`undo_device_control` |

执行器每次提交动作前检查空间锁与进程所有权连接是否仍有效。检测到连接失效就停止发送后续动作。停止不等待执行锁，因此能抢占一批动作的后续部分；它不能撤回已经发送的单个动作。网络分区检测的时效、检查后立即断连的竞争窗口、数据库故障下的可用性没有被这些测试完全覆盖。

## 故障实验验证什么

`backend/tests/test_http_replicas.py` 启动真正的两个 Uvicorn API 子进程、独立网关进程及 HTTP 故障代理，共享专用 PostgreSQL。8 个场景不是线程调用冒充 HTTP 部署：

1. A 控灯，B 看到相同数值，B 撤销后 A 也看到原值。
2. A 等待动作回复时启动 B，B 不清理 A 的活跃动作；B 停止服务后，A 不再发剩余动作。
3. 同计划重复确认、不同计划竞争均被空间执行锁拦住；执行结束后重复确认只读取结果。进行中演示重置返回 `SPACE_BUSY`。
4. 网关已提交后丢回复，再杀死并重启网关；B 从持久化回执核对成功，设备版本不增加。
5. A 在网关提交后崩溃；B 启动只恢复死亡所有者，标记未知；核对后补回计划结果，不执行剩余动作。
6. 网关离线时仍保存停止事实，设备状态显示未确认；不假装网关已接受停止代次。
7. A 执行中将测试 Redis 租约缩短至 50 ms 并等过期；B 的不同计划和直接控制仍被 SQL 锁拒绝。
8. 切断 Redis TCP 连接，重复上述竞争；批次完成后，在 Redis 仍不可用时，新显式控制可以正常执行。

网关另有 10 项测试，覆盖持久化、16 个并发同 actionId、参数/设备校验、重置不删除回执、Bearer 校验和真实 HTTP 进程重启。回执核对专项还验证不能把迟到 unknown 回调追加成第二条结果。浏览器场景只注入“未知”的响应以检查页面；真正的断连与崩溃由上述后端测试制造，两种证据不要混说。

## 怎样运行

从仓库根目录，设置一个仅保留在本机的 `LIVINGMIND_GATEWAY_TOKEN`，然后执行：

```bash
docker compose -f compose.yaml -f compose.gateway.yaml --profile replicas up -d --build
```

API A 默认 `127.0.0.1:8000`，API B 为 `127.0.0.1:8001`。网关没有发布宿主机端口，API 用运行时 Bearer token 访问它。网关不是生产认证方案，App 的演示身份也不是正式登录；不要部署到公网。普通 `docker compose up` 保留原单实例进程内网关，不等于自动启用多实例。

首次切换模式，应先停止旧 API，再迁移到 `0007` 并同时启用所有副本；不要将旧进程内网关实例与共享网关实例混跑。旧行没有 ownerId，升级时按旧版遗留工作处理。回滚前也应停 API；降到 `0006` 会删除 ownerId 和共享设置表，失去其撤销窗口与能源模式数据，因此先备份，不能对演示/正式数据库随手运行测试回退。

隔离测试使用 `livingmind-eval` 项目，PostgreSQL 55432、Redis 56379/15。**pytest 会清空指定测试库，不能指向有用数据。** 在 `backend/` 运行：

```bash
LIVINGMIND_TEST_STORE=sql \
LIVINGMIND_TEST_DATABASE_URL=postgresql+psycopg://livingmind:livingmind@127.0.0.1:55432/livingmind \
LIVINGMIND_DATABASE_URL=postgresql+psycopg://livingmind:livingmind@127.0.0.1:55432/livingmind \
LIVINGMIND_TEST_REDIS_URL=redis://127.0.0.1:56379/15 \
LIVINGMIND_REDIS_URL=redis://127.0.0.1:56379/15 \
python -m pytest -q -p no:cacheprovider tests/test_http_replicas.py tests/test_persistent_gateway.py
```

Python 用 3.11/3.12，依赖按仓库 constraints 安装。测试中的 token、人物、设备和话术全部为模拟数据，不调用付费模型。停止本任务容器用对应项目和两个 Compose 文件的 `down`；不加 `-v`，数据卷保留。

## 仍然要保留的限制

- PostgreSQL 是单节点，虚拟网关是单进程 SQLite，不是高可用集群；尚无容量或长期负载结论。
- 恢复在 API 启动时扫描，不是常驻故障回收器；仍运行的实例不会自动代替死亡实例续跑服务。
- 共享网关模式的重置拒绝正在写设备的批次。跨进程任意时刻的重置、停止、创建计划混合竞争还需更多验证，不是跨数据库与网关的原子重置。
- 只读核对页针对计划动作；直接面板控制和撤销虽经过同一网关并持久化回执，尚未提供同等完整的用户侧未知动作核对入口。
- 核对只补齐历史结果，不自动让失败服务恢复 active，也不自动继续余下步骤。
- 网关快照和 PostgreSQL 必须一致备份/恢复；不要单独把业务库恢复到旧代次后声称正常恢复，较新的网关会拒绝旧命令。
- 真机、真实语音识别、真实 SpaceMind/厂商设备、生产鉴权和真实定时调度仍需独立验收。

## 面试时怎样讲

可以说：“以前设备状态在 API 内存里，重启和多实例会对不上。我把虚拟网关独立出来，持久化设备状态和动作回执；用两个真实 API 进程模拟丢回复、进程崩溃和 Redis 失效，验证重复请求不会再次写设备，停止也能阻止后续动作。对于无法确定的结果，页面允许查询回执，不盲目重试。”

随后主动补一句：“这是对虚拟设备的故障验证，真实硬件还要支持对应的幂等和查询协议。”先亲自跑一个实验、读清对应代码，再按实际参与程度描述个人贡献。

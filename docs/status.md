# 实现状态

> **2026-10-03 独立网关批次已发布**：最终业务代码 **a3594c1**，CI [37114091256](https://github.com/Hector-sau/Livingmind/actions/runs/37114091256) **六项通过**。已增加持久化 HTTP/SQLite 虚拟网关、双 API 故障测试、ownerId 恢复、SQL 执行锁、共享撤销/能源模式、页面核对，以及网关离线时仍保存停止事实。CI 默认后端 **210/42**、SQL+legacy **242/10**、全栈 **251/1**、前端 **101/101**、契约、迁移、Docker 浏览器 **28/28**；本机最终 Docker+LangGraph 浏览器也 **28/28**，iOS/Android JS 导出通过。uuid 已修补，仍有两个根依赖公告未解决。详见 [交接](../AGENT-HANDOFF.md)、[独立网关](durable-gateway.md)、[依赖风险](dependency-risk.md)。下文旧数字保留为历史；v3 人工审核、安装包/真机与真实设备仍未完成。

> **2026-10-03 当前回归**：默认后端 **170 通过 / 33 跳过**；SQL+legacy **195/8**；SQL+Redis+LangGraph **202/1**；全栈唯一跳过项为内存专属断言。前端类型检查与 **92/92**、契约一致、本地内存浏览器 **28/28** 已通过。GitHub 提交 `7867d9c` 的 [CI 37038661216](https://github.com/Hector-sau/Livingmind/actions/runs/37038661216) **6/6 Job 全绿**，三套后端数字一致，Docker 浏览器 **28/28**。原始证据为 `docs/evidence/engineering-regression-2026-10-03.xml` 和 `docs/evidence/github-ci-37038661216.json`；真机仍未验。

> 指标口径：本文件早期“只有一次真实 DeepSeek 调用”的描述属于历史记录。可核对证据包含 `docs/evidence/model-latency-*.json` 的历史 96 次，以及 `holdout-v2-model-paired-2026-10-02.json` 的新增 24 次交错调用；详见 `docs/interview-evidence-2026-10-02.md`。F+G 的旧测试数只作历史基线。

> 本轮新增：独立模拟路由集 29/30；交错模型对照 chat 11/12 通过方向性语义检查、flash 9/12，分别 0/3 次降级。两服务进程共享虚拟网关验证并发确认、停止、崩溃、Redis TTL 与 TCP 断连；三种网关回执丢失均持久化 unknown 且不重发。Outbox 迁移 0006 升降通过，验证并发写入/发布/消费、死信重投和迟到事件。请求 ID 与 Agent 分段、动作及写入/回读日志已关联。细节和限制统一见证据主索引，不能沿用历史 GitHub 6/6 作为本提交的结果。

> **Docker 交付验收补充**：最终 unknown 展示已在 GitHub Docker 浏览器 **28/28** 验证，使用 PostgreSQL + Redis + 默认 legacy 编排和两个事件 Worker；LangGraph 由全栈后端 Job 覆盖。本机此前 LangGraph 容器浏览器 **27/27**，其队列快照 pending=0、dead_letters=0、投递事件/消费回执各 74。随后本机 Docker 内部元数据打开缓慢，授权重启后仍未恢复，不能将 CI 通过说成本机修复。0006→0005→0006 本地迁移与 CI head→0002→head 均通过。模型路径使用本地桩，真实硬件未接入。

> **界面收尾**：成功、未知、失败、拒绝和跳过分别显示；unknown 不再误报“已为你调整好”或“未执行”。`conversation.test.ts` 新增 4 条测试，`http-unknown-receipt` 为响应注入型展示测试；传输故障与不重发由后端故障用例独立验证。

更新：2026-09-19 · 第一批、⑤–⑨演示能力、稳定性收尾、能源快照、**T1–T6 工程化冻结**与 **F 受控执行专项**均已完成。Experience Agent 已在用户 Mac 验证一次真实 DeepSeek 调用（deepseek-flash，2035 ms）。仍待外部条件：iPad / 安卓平板真机构建与录屏、SpaceMind / 厂商真实设备对端。

## 已实现

| 能力 | 位置 | 证据 |
|---|---|---|
| 实施基线文档 | `README.md`、`docs/` | — |
| Expo App 骨架（平板横竖屏、可配置后端地址） | `apps/mobile/app.json`、`config.ts` | `tests/config.test.ts` |
| FastAPI 骨架 + 健康检查 | `backend/app/main.py`、`api/health.py` | `tests/test_health.py` |
| 数据契约 + 统一错误格式 | `backend/app/contracts/`、`api/errors.py` | `tests/test_contracts.py` |
| 契约生成前端类型 | `scripts/gen-api.sh` → `packages/api-client/` | CI `contracts` 任务 |
| 种子人物（2 人偏好不同）、演示账户 | `backend/app/demo/seed.py` | `tests/test_seed.py` |
| 可点击原型：人物 → 需求 → 计划 → 确认 → 设备 → 停止 → 服务动态 | `apps/mobile/features/` | 浏览器自动点击（见下） |
| 前端模拟接口（与后端规则一致，标注“前端模拟”） | `apps/mobile/services/mock/` | `tests/mockApi.test.ts` |
| 真实 API 客户端（断网/超时明确报错，不回退模拟） | `apps/mobile/services/http/` | `tests/httpApi.test.ts` |
| P07：固定日家庭能源离线仿真（规则 vs 单智能体 MATD3）只读 API 与空间页展示 | `simulation/home-energy/`、`backend/app/energy/simulation.py`、`features/energy/OfflineSimulationCard.tsx` | `tests/test_offline_energy_simulation.py`（2 项）、`tests/mockApi.test.ts` |
| P07：该固定日结果在本仓库复现（同一权重、种子 42，8 项 KPI 全部一致，最大差 0.005；未重新训练） | `simulation/home-energy/research/reproduce_day.py`、`data/reproduced-day-comparison.json` | 复现脚本可一条命令重跑；依赖单独列在 `requirements-research.txt`，不进后端与 CI |
| 固定休息规则（无模型） | `backend/app/rules/rest_rule.py` | `tests/test_rest_flow.py` |
| 受控执行：PolicyDecision、用户确认后的有界 ExecutionGrant、逐动作 guard、持久化动作账本、Gateway 回执与回读 | `backend/app/harness/`、`adapters/gateway.py`、`repositories/` | `tests/test_execution_authority.py`（8 项）与原有流程回归 |
| 有状态虚拟设备（灯光、空调、窗帘） | `backend/app/adapters/virtual/devices.py` | 同上 |
| 设备 V2 契约已在虚拟执行路径落地（`actionId` 幂等、`serviceEpoch` fencing、受理/完成/失败/拒绝/未知回执）；语音与传感器仍是接口预留 | `backend/app/adapters/protocol.py`、`gateway.py`、`voice.py`、`events.py` | 虚拟网关有幂等/并发/过期代次测试；**未接入真实设备、SpaceMind、音箱或传感器** |
| 服务状态、确认幂等、单空间单服务、停止失效、计划过期 | `backend/app/services/rest_service.py` | 同上 |
| 活动记录（按实际发生写入，标注来源） | 同上 | 同上 |
| PR 模板 + CI（三套后端组合、迁移升降、契约、前端与 Docker API E2E） | `.github/` | GitHub Actions 最新运行 `35409969801`（`bfcdd0e`）：6/6 Job 通过 |
| B：设备写入在服务锁外执行；停止可中途抢占慢设备批次 | `backend/app/services/rest_service.py`、`adapters/virtual/devices.py` | `tests/test_concurrency.py`（服务层 + HTTP 线程池各一） |
| ⑤：Experience Agent（提示词、Pydantic 输出校验、DeepSeek Provider） | `backend/app/agents/experience/` | `tests/test_experience_agent.py`（14 项，用测试替身，不调 DeepSeek） |
| ⑤：规则/模型切换、降级为规则并标注原因、延迟记录 | `backend/app/services/planner.py`、`rules/rest_rule.py` | 同上；本地 HTTP 桩验证了真实 HTTP 路径与 2 秒超时降级 |
| ⑤：App 计划来源开关、四种来源标签、降级原因、模型/延迟信息 | `apps/mobile/features/rest/ModeToggle.tsx`、`PlanCard.tsx` | 网页端到端 `http-model-paths`、`mock-model-fallback` |
| R1：模型计划偏离上限（灯光/窗帘 ±40、空调 ±3°C），超出降级 | `backend/app/services/planner.py` | `tests/test_experience_agent.py`（超限 3 例 + 恰好在上限 1 例）；网页端到端 |
| R1：兜底异常 → `INTERNAL_ERROR`，不泄露细节 | `backend/app/api/errors.py` | `tests/test_rest_flow.py` |
| R1：App 计划请求超时 = 后端模型超时 + 3 秒 | `apps/mobile/services/http/httpApi.ts` | `tests/httpApi.test.ts` |
| R1：计划过期提示每 15 秒重新计算；模拟模式措辞修正；重置写入 `demo_reset` | `features/rest/useRestFlow.ts`、`ModeToggle.tsx`、`rest_service.py`、`mockApi.ts` | 前后端测试 |
| R1：网页端到端脚本入库（7 个场景，一条命令） | `apps/mobile/e2e/` | `python apps/mobile/e2e/run_e2e.py`：7/7 通过 |
| ⑥：模拟室温事件接口 `POST /api/spaces/{spaceId}/events`；冷却 30 秒、上限 3 次、单服务单调整、停止后忽略；规则调整（±1°C，不超出偏好 ±3°C）；模型调整跟随服务模式并受偏离上限约束 | `backend/app/services/rest_service.py`、`services/planner.py`、`rules/rest_rule.py` | `tests/test_events.py`（10 项，含停止与调整并发） |
| ⑥：App“注入模拟事件”按钮、调整次数、事件结果提示、服务动态中的事件记录；前端 Mock 同步规则 | `apps/mobile/features/rest/ServiceCard.tsx`、`services/mock/mockApi.ts` | `tests/mockApi.test.ts`；端到端 `mock-event`、`http-event` |
| E：意图路由识别否定、冲突与指代不清（“我不想休息，只想关灯”走设备指令；“先开灯再关灯”与“把那个调低一点”先澄清，不产生动作） | `backend/app/agents/orchestrator/agent.py::route_intent`、`clarification_question` | `tests/test_agents.py`（新增 3 项路由与澄清用例） |
| E：可恢复的多轮澄清。`conversationId` + `PendingClarification` 落库（内存或 PostgreSQL），按账户、人物、空间、会话四重隔离，10 分钟过期，可取消；补充信息后按原意图继续，中途换人物不会被别人的待澄清污染 | `backend/app/contracts/models.py::PendingClarification`、`repositories/store.py`、`sql_store.py`、`alembic/versions/0004_pending_clarifications.py`、`services/rest_service.py` | `tests/test_agents.py`（澄清 → 恢复 → 取消 → 人物隔离）、`tests/test_experience_agent.py`（模型给出澄清问题时不生成计划） |
| E/F：启动恢复可查询。`GET /api/system/recovery` 返回存储类型、活跃服务数、被取消的结果未知步骤数、清理的执行中标记数、`unknown` 动作数和设备对账状态 | `backend/app/services/rest_service.py::recovery_status`、`api/routes.py` | `tests/test_recovery.py`：崩溃遗留步骤不重放；已 dispatch/accepted 但无终态的动作改为 `unknown` |
| ⑥b：四个入口（对话 / 空间 / 场景 / 我的）；对话主页（计划卡、结果卡、系统消息、服务状态条、快捷语、语音占位）；平板左栏 + 右侧房间面板，手机底部标签栏 | `apps/mobile/features/shell/`、`chat/` | `tests/conversation.test.ts`；端到端全部场景已改为走对话 |
| ⑥b：演示 PIN 切换人物（`POST /api/persons/{id}/unlock`，不是认证）、访客模式（空间默认设置）、只显示本人偏好、证据面板开关 | `backend/app/services/rest_service.py`、`apps/mobile/features/me/` | `tests/test_people_and_scenes.py`；端到端 `*-pin-evidence`、`http-guest-scenes` |
| ⑥b：场景库（`GET /api/scenes`，状态如实）与人话时间线 | `backend/app/demo/seed.py`、`apps/mobile/features/scenes/` | `test_scene_library_status_is_honest`；`tests/conversation.test.ts` |
| ⑥b：演示与测试数据重新设计（3 位成员 + 访客、场景库、事件序列、15 条 Experience Agent 评测用例与打分） | `backend/app/demo/seed.py`、`backend/evals/`、`docs/test-data.md` | `tests/test_eval_cases.py` |
| C：天蓝色明亮主题、LivingMind Logo（头部、App 图标、启动图、AI 头像）、统一图标、渐变按钮、柔和阴影、入场/呼吸/数值条动画（尊重减弱动态效果）、骨架屏 | `apps/mobile/theme/`、`components/`、`features/**`、`assets/` | 端到端 12/12（C 当时）；截图见 `apps/mobile/e2e/.out/screens/`（本地生成，不入库） |
| ⑧：主 Agent（规则路由 + 编排 + 协作轨迹）；完整分支 记忆 → Experience → 能源 → Space Execution → Harness；简化分支（设备指令）；状态查询与范围外回答 | `backend/app/agents/orchestrator/`、`POST /api/assistant/messages` | `tests/test_agents.py`；端到端 `mock-agents`、`http-agents` |
| ⑧：Space Execution Agent（设备能力、夜间灯光上限、动作生成、中文设备指令解析） | `backend/app/agents/space_execution/` | 同上（解析 6 例、能力缺失、规则限幅） |
| ⑧：人物记忆（本人偏好读取与编辑、空间规则；共享列表不含偏好） | `backend/app/memory/`、`GET /api/memory`、`PUT /api/memory/preference`；“我的”页编辑 | 同上；端到端 `http-energy-memory` |
| ⑧：能源智能（舒适范围、分时电价、估算负荷档位、舒适优先 / 节能模式） | `backend/app/energy/`、`PUT /api/spaces/{id}/energy-mode`；计划卡与空间页 | 同上 |
| ⑧：Harness 规划预检；协作过程展示（计划卡“查看协作过程”） | `backend/app/harness/policy.py`、`apps/mobile/features/agents/TraceView.tsx` | 同上 |
| ⑨：一键“准备演示”（重置数据 → 林悦 · 舒适优先 · 设备初始 80/26/100 · 清空对话 · 关闭证据面板 · 回到对话页） | `apps/mobile/features/shell/AppShell.tsx`、`features/me/MeScreen.tsx`、`useRestFlow.resetDemo` | 端到端 `http-prepare-demo` |
| ⑨：“场景”页“1+2 Agent 如何协作”说明卡（措辞与交接文档 0.4 一致；有计划时展示真实协作过程，否则引导去对话） | `apps/mobile/features/scenes/ScenesScreen.tsx` | 同上 |
| ⑨：信息类提示 3 秒自动淡出（警告、错误常驻）；空态改为大图标 + 引导语（对话、服务、设备、证据、场景时间线） | `features/shell/notices.ts`、`components/EmptyState.tsx` | `tests/notices.test.ts`；端到端 `http-prepare-demo` |
| ⑨：3 分钟演示讲稿 | `docs/demo-script.md` | — |
| ⑦：整晚安排（5 步：23:00 关灯、01:00 空调 +1°C、所选起床时间前 30 / 15 / 0 分钟三步唤醒），Space Execution Agent 规则生成、Harness 预检、随休息计划确认 | `backend/app/rules/night_rule.py`、`agents/space_execution/agent.py` | `tests/test_night_service.py` |
| ⑦：模拟时钟推进与模拟入睡；锁内认领保证每步只执行一次；时钟与事件自动操作互斥；停止取消剩余步骤；任一设备动作失败时该步取消，全部动作成功才 `completed`；重置隔离在途旧任务 | `backend/app/services/rest_service.py`、`adapters/virtual/devices.py` | `tests/test_night_service.py`（15 项）、`tests/test_concurrency.py`；前端 Mock 同步 `tests/night.test.ts` |
| ⑦：App 运行条“快进 / 自动播放整晚”、计划卡整晚安排、空间页整晚时间线、对话系统消息；场景“起床渐进唤醒”改为已实现；场景时间线按触发来源归类动作 | `apps/mobile/features/night/`、`features/chat/ServiceStrip.tsx`、`features/scenes/timeline.ts` | 端到端 `http-night`、`mock-night`、`http-night-stop-phone`；`tests/conversation.test.ts` |
| D：三段网页版演示录屏（字幕标注网页版 / 虚拟设备 / 规则模式） | `apps/mobile/e2e/record_demo.py` | 已生成 `01-user-trigger`、`02-event-adjust`、`03-night-stop`（mp4，不入库；已放到用户 Mac 的 `Livingmind/演示打包/`） |
| D：汇报主张与证据对照表（28 条，含 T1–T6 工程证据） | `scripts/build_evidence.py` → `docs/evidence.md`、`output/pdf/` | 2026-09-18 重新生成并逐页渲染检查；PDF 5 页 |
| D：平板安装说明与开发版配置（`eas.json`、`expo-dev-client`、包名 `com.livingmind.demo`、iOS 本地网络设置） | `docs/device-build.md`、`apps/mobile/eas.json`、`app.json` | **未实际构建**；iOS / Android JS 与 Hermes 导出成功；网页端到端 20/20 通过 |
| 真实模型端到端脚本（后端：5 句话 → 计划 → 确认 → 回读 → 停止，延迟统计；浏览器：`--real-model`） | `backend/scripts/e2e_real_model.py`（含 `--eval`）、`apps/mobile/e2e/run_e2e.py --real-model` | 已用本地桩空跑通过；真实模型运行为**可选项**（开发环境无法访问 api.deepseek.com，需在用户 Mac 终端运行） |

## 步骤 4 的 7 项验证

| # | 内容 | 结果 |
|---|---|---|
| 1 | 创建计划不改变设备 | 自动化测试通过 |
| 2 | 确认后后端状态改变，App 能读回 | 自动化测试 + 浏览器点击（后端模式）通过 |
| 3 | A/B 人物计划不同 | 自动化测试 + 浏览器点击通过 |
| 4 | 重复确认不重复执行 | 自动化测试通过 |
| 5 | 停止后旧请求不再产生动作 | 自动化测试通过。B 之后：停止能在慢设备写入进行中立即返回，已开始的动作完成、其余跳过（`tests/test_concurrency.py`） |
| 6 | 非法人物 / 空间 / 账户 / 参数 / 过期 / 版本不符被拒绝 | 自动化测试通过 |
| 7 | 后端断开时 App 明确反馈 | 前端单元测试 + 端到端场景 `http-offline`（关掉后端后点确认，出现“无法连接后端，显示的状态可能已过期”，设备数值变灰，没有假装成功） |

浏览器端到端：`apps/mobile/e2e/run_e2e.py`（已入库，可复现）。用 Expo 网页导出，在 1180×820 和 390×844 两种尺寸下跑 27 个场景。2026-09-18 通过 `--external-backend` 连接 Docker Compose API 跑过 **20/20**（当时 20 个场景）；2026-09-19 新增两个澄清场景后本地 22/22 通过；同日 G 专项新增语音 2 个、直接控制 3 个场景后本地 **27/27 通过**；末尾断网场景只关闭本地代理，不伪造后端成功。模型路径连的是本地桩，不是 DeepSeek。

## ⑤ 的验证情况

| 要求 | 结果 |
|---|---|
| 合法模型输出 → 计划，创建阶段不改设备 | 测试通过 |
| 模型计划确认后经同一执行器并回读 | 测试通过 |
| 模型超时 → 规则降级并标注 | 测试通过；本地 HTTP 桩 + 2 秒超时实测降级 2.07 秒 |
| 非法 JSON、越界、未知字段不能绕过校验 | 6 种输入参数化测试通过；另有偏离上限 4 例 |
| A/B 人物提示词各用自己的偏好 | 测试通过 |
| 规则模式完全不请求模型 | 测试通过 |
| 模型失败不影响停止、重复确认、过期 | 测试通过 |
| 日志与错误不含 API key | 测试通过 |
| **真实 DeepSeek 调用与 8 秒目标** | **Agent 层已验证**（用户 Mac，2026-09-17）：`deepseek-flash`，Agent 一次调用 **2035 ms**，输出通过结构校验（灯光 15%、空调 24°C、窗帘 0%，理由引用了“有点热”并相对基线下调 1°C）。单次样本。多次统计与评测集打分是可选项（脚本已就绪），汇报时引用单次结果并说明 |

本地 HTTP 桩只用于验证请求格式（`/chat/completions`、Bearer 头、`response_format: json_object`）、响应解析和超时路径，**不代表已连通 DeepSeek**。

## F 受控执行专项（2026-09-19）

| 机制 | 实现 | 实测证据 |
|---|---|---|
| 可审计策略决策 | 计划预检产生 `PolicyDecision`，包含规则结果、计划语义哈希和是否需确认 | 确认响应和 PostgreSQL 均保存决策 |
| 有界执行授权 | 用户确认后才生成 `ExecutionGrant`，绑定 account/person/space/plan/version/hash/service/epoch/capability/有效期；停止或结束撤销 | `test_confirmation_creates_policy_grant_and_completed_action_ledger`、`test_grant_scope_can_be_narrower_than_platform_policy` |
| 动作账本 | `ActionExecution` 保存 `pending → dispatching → accepted → terminal`、尝试次数、观测值和错误 | 内存 / PostgreSQL 两种存储一致；迁移 `0005_execution_authority.py` 可升降 |
| 网关幂等与 fencing | 同 `actionId` 同载荷返回原回执；并发重试先占位、不重复写；同 ID 不同载荷拒绝；旧 `serviceEpoch` 命令在写设备前拒绝 | `tests/test_execution_authority.py`（8 项） |
| 结果未知处理 | 网关受理后无终态时记为 `unknown`；重启不盲目重发 | `tests/test_recovery.py`、`test_accepted_without_terminal_receipt_is_unknown_and_recorded` |

F 专项当时的回归：后端内存 + legacy 144 passed / 19 skipped；PostgreSQL + Redis + LangGraph 162 passed / 1 skipped；前端 32 passed；Alembic `0004 → 0005 → 0004 → 0005` 通过；浏览器端到端 22/22。**与 G 专项合并后重跑的最新值见下方“F+G 合并回归”。**Docker 镜像重新拉取基础镜像时受 Docker Hub 元数据超时影响，本轮用已存在镜像 + 当前源码挂载完成容器验证。

## 未验证 / 限制

- **未在 iPad、安卓平板或手机真机上运行**，也未在 iOS 模拟器上运行；上面的界面验证来自网页版（react-native-web），真机效果需要团队用 Expo Go 确认。
- 未配置 `LIVINGMIND_DATABASE_URL` 时使用内存模式，后端重启即重置；Compose 默认使用 PostgreSQL，人物偏好、计划、服务、动作、活动和事件会持久化。虚拟设备适配器的即时状态仍属于单个 API 进程，不代表真实硬件状态。
- 身份只是演示账户，没有正式认证；后端不要部署到公网。
- 设备全部是虚拟的，不代表真实硬件接入。
- 模拟事件没有真实传感器；室温数值由按钮或 API 直接给出。
- 整晚服务跑在模拟时钟上，由按钮或“自动播放”（每 2.5 秒推进一步）驱动；后端没有真实定时器，也不读真实时间。
- 演示 PIN 不是认证；“我的”页上直接写出了演示 PIN，便于评审操作。
- 语音按钮仍是占位，点击只提示“后续接入”；后端已有 `VoiceGateway` 转写与播报协议（含说话人与空间提示字段），但没有麦克风、唤醒词、说话人到人物的授权映射或音箱接入。真实语音的可信身份必须由应用层解析，不能由转写文本自称。
- Logo 来自团队既有的 LivingMind 品牌源文件（用户已同意在 App 中使用），为 PNG；正式发布前按品牌说明补 SVG 母版与商标检索。
- 所有人物、偏好、评测用例、室外温度与电价时段都是设计的模拟数据（见 `docs/test-data.md`）。
- 主 Agent 路由与 Space Execution Agent 的指令解析是规则实现；只有 Experience Agent 可调用模型。
- 能源负荷是规则估算，不是实测，也不代表节省比例。
- P07 的能源数值是固定预设日的离线结果：单智能体、美元/华氏度参数，未重训，未接入实时设备；不得外推成真实节能效果。该日结果已在本仓库复现（`simulation/home-energy/research/reproduce_day.py`，种子 42，8 项 KPI 与图一致，最大差 0.005）。
- 演示身份下，谁能读哪份记忆由请求上下文决定，不是认证。
- 规则模式下输入文字只记录，不做语义理解。模型模式已验证一次真实调用；延迟只有单次样本。
- GitHub Actions 已真实运行；最新是 `main@bfcdd0e` 对应的运行 `35409969801`，6 个 Job 全绿（4m30s）。
- 虚拟 `DeviceGateway` 已验证 `actionId` 幂等与 `serviceEpoch` fencing，但真实厂商网关、多 API 实例的锁续租、硬件回执对账、真实后台定时器和传感器事件源仍未做；不宣称真实设备“恰好执行一次”。
- 澄清只覆盖否定、设备冲突和指代不清三类规则可判定的歧义，不是通用多轮对话；虚拟设备状态仍在进程内，不跨进程恢复。

## T1 Docker 基线（已完成并通过宿主机验证）

| 项 | 位置 | 状态 |
|---|---|---|
| 后端镜像（Python 3.12、多阶段、非 root、依赖版本锁定） | `backend/Dockerfile`、`backend/constraints.txt`、`backend/.dockerignore` | Docker Desktop 实际构建通过；镜像 96,471,430 bytes；运行用户为 `livingmind`；镜像内 `.env` 数量为 0 |
| Compose（PostgreSQL → migration → API，Redis 健康检查；端口只绑 `127.0.0.1`） | `compose.yaml` | `docker compose config`、依赖启动顺序、数据库迁移、Redis与API健康检查均通过；能源结果JSON以只读方式挂载 |
| 一键验证脚本（构建 → 容器内测试 → 健康检查 → 宿主机走完休息闭环 → 关闭） | `scripts/verify-t1.sh` | 2026-09-18 在用户Mac完整通过；失败时自动清理容器；使用独立PostgreSQL/Redis宿主端口避免冲突 |
| 锁定版本在 Python 3.12 上的可用性 | `backend/constraints.txt` | 已验证：安装成功，全部后端测试在 3.12 上通过 |

宿主机证据：Docker 29.6.2、Compose 5.3.1；容器内默认模式 127 通过 / 18 跳过；API `healthy`；宿主机完成“计划 → 确认 → 灯光回读15% → 停止 → 重置”；脚本结束后Compose栈已关闭。唯一警告是Starlette TestClient使用AnyIO旧别名，不影响结果。日志在本机忽略目录 `dist/t1-verify.log`。

## T2 PostgreSQL 持久化（单实例已完成）

| 项 | 位置 | 证据 |
|---|---|---|
| 同步数据库栈：SQLAlchemy 2 + psycopg 3 + Alembic；`LIVINGMIND_DATABASE_URL` 为空时完全走内存，行为不变 | `backend/app/db/`、`backend/alembic/`、`backend/app/config.py` | 未配数据库时原有测试全部不变；配上数据库后新增专项测试一起通过 |
| 人物偏好持久化：Repository 协议 + 内存实现 + SQL 实现；种子只在缺行时写入，不覆盖用户编辑 | `backend/app/memory/repository.py`、`app/memory/service.py` | `tests/test_persistence.py`：同一套契约测试跑内存与 PostgreSQL 两种实现 |
| 重启后偏好仍在；演示重置回到种子值；接口层在配置数据库时自动使用 SQL 实现 | `RestService(preferences=...)`、`default_preference_repository()` | 同上（真实 PostgreSQL 16 上运行） |
| 迁移 `0001_person_preferences`（含数值范围 CHECK 约束） | `backend/alembic/versions/` | `alembic upgrade head` 在 PostgreSQL 16 上执行通过 |
| Compose 增加 `postgres` 与一次性 `migrate` 服务，API 等迁移成功后再启动 | `compose.yaml` | 宿主机验证通过：PostgreSQL健康后迁移成功退出，随后API启动并达到healthy |
| 业务事实落库：计划、服务、整晚步骤、动作结果、活动记录、空间代次、进行中标记 | `backend/app/repositories/store.py`（协议 + 内存实现）、`sql_store.py`、`alembic/versions/0002_business_facts.py` | 整套测试换存储再跑一遍：`LIVINGMIND_TEST_STORE=sql` 下 125 项通过；不配数据库时 117 项通过、8 项跳过 |
| 数据库层约束：每空间只有一个 active 服务（部分唯一索引）；夜间步骤 `UPDATE … WHERE status='pending' RETURNING` 只认领一次 | 同上 | `tests/test_persistence.py`：绕过服务层直接插入第二个 active 服务被数据库拒绝；两个连接并发认领，每步只被认领一次 |
| 重启恢复：新进程能读到运行中的服务、整晚步骤状态、活动记录，并能继续停止 | 同上 | `test_plans_services_steps_and_activity_survive_a_restart` |
| 网页端到端在两种存储下各跑一遍 | `apps/mobile/e2e/run_e2e.py` | 内存模式 20/20；后端接 PostgreSQL 再跑一遍同样 20/20 |

未做：跨实例协调（多 API 实例同时写）仍依赖单进程锁 + 数据库约束，要到 T4 才补 Redis；设备状态仍在内存虚拟适配器里（它模拟硬件，不是业务事实）。

## T3 LangGraph 规划图（规划分支已完成）

| 项 | 位置 | 证据 |
|---|---|---|
| 编排器拆成阶段方法（记忆 / 体验 / 能源 / 执行 / Harness / 组装计划），legacy 与 graph 共用，不复制规则 | `backend/app/agents/orchestrator/agent.py` | 拆分后原有测试全部通过 |
| LangGraph `StateGraph`：路由 + 四条分支；依赖（设备适配器、id 生成器）不进入状态，因此 checkpoint 可序列化 | `backend/app/graph/builder.py`、`state.py` | `tests/test_graph_orchestrator.py`（8 项） |
| 开关 `LIVINGMIND_ORCHESTRATOR=legacy\|langgraph`；图路径不执行设备，仍需确认 | `backend/app/config.py`、`app/graph/runtime.py` | 图路径下整套测试通过；`test_graph_plans_without_touching_devices` |
| 等价定义与对照器（忽略 id / 时间戳 / 耗时，比意图、摘要、动作、整晚安排、能源、节点顺序） | `backend/app/graph/compare.py`、`scripts/compare_orchestrators.py` | 5 组输入全部等价；跨 3 位人物 × 3 句话的等价测试 |
| checkpoint：无数据库用内存 saver，有数据库用 `PostgresSaver` 自建表 | `app/graph/runtime.py` | 图 + PostgreSQL 组合下 133 项测试通过；数据库中出现 `checkpoints` 等表 |

未做：事件调整仍走 legacy 单阶段；图只覆盖规划，不覆盖执行（执行属于 Harness 与执行器）。

## T4 Redis 协调（已完成）

| 项 | 位置 | 证据 |
|---|---|---|
| 空间执行锁：随机 token + 30 秒 TTL，释放时用 Lua 校验 token，只删自己的锁 | `backend/app/cache/locks.py`、`keys.py` | `tests/test_cache_coordination.py`：持有者唯一、别人的锁不会被误删、TTL 存在 |
| 第二个 API 实例在空间被驱动时收到 `SPACE_BUSY`，释放后同一计划仍可确认 | `app/services/rest_service.py::confirm_plan`、`advance_clock` | 同上 |
| 事件冷却的快速判断：Redis 键带 TTL，删掉它也不会绕过规则（服务行仍是权威） | `app/cache/cooldown.py` | 同上 |
| 降级：未配置 Redis、或配了但连不上，都不影响主流程 | `app/cache/client.py` | `test_without_redis_...`、`test_unreachable_redis_degrades_instead_of_failing` |
| 与其他两层组合运行 | — | PostgreSQL + LangGraph + Redis 同时开启，145 项后端测试通过 |

未做：设备状态缓存（会带来过期风险，收益为零）；幂等结果缓存（数据库已幂等）。

## T5 Outbox 与事件总线（数据库队列实现已完成）

| 项 | 位置 | 证据 |
|---|---|---|
| 事件信封（`event_id`、`schema_version`、`correlation_id`、`spaceId` 保序）与 10 种领域事件 | `backend/app/events/envelope.py` | `tests/test_outbox_events.py` |
| 业务事实与 outbox 行同一事务提交；事务回滚则事件也不存在 | `app/repositories/sql_store.py::_write_events`、`app/services/rest_service.py` | `test_business_facts_and_events_commit_together`、`test_a_failed_transaction_leaves_no_event` |
| Publisher：`FOR UPDATE SKIP LOCKED` 领取、至少一次投递、重复投递不产生重复行、失败退避、超限进死信不删除 | `app/events/outbox.py`、`workers/outbox_publisher.py` | `test_publisher_delivers_once_and_marks_rows`、`test_bus_outage_keeps_events_and_never_blocks_devices` |
| Consumer（activity-projector）：按 `event_id` 去重、投影到 `service_projection`、同空间事件保序 | `workers/activity_projector.py` | `test_projection_is_idempotent_and_ordered` |
| 总线停摆不影响设备执行与停止；活动记录仍由 API 同步写库 | 同上 | 同上 |
| Compose 增加 `outbox-publisher` 与 `activity-projector` 两个 worker | `compose.yaml` | 宿主机常驻运行验证：7/7 Outbox 发布与消费；重启两个 Worker 后事件与回执数不变 |

未做：Kafka 实现（按用户决定，非必要不上常驻中间件；接口已留在 `EventPublisher`）。

## T6 本地集成与冻结（已完成）

- Compose 全栈一次启动：PostgreSQL、Redis、migration、API、Outbox Publisher、Activity Projector 均健康。
- 迁移：空库 0001→0003，以及 0003→0002→0003 回退再升级通过。
- 后端组合（T6 冻结当时）：内存+legacy `127 passed / 18 skipped`；PostgreSQL+legacy `141 passed / 4 skipped`；PostgreSQL+Redis+LangGraph `145 passed`。E 专项后的基线见下节。
- Redis 测试仅允许清理显式配置的非 0 号逻辑库；冷却到期同时尊重服务时钟与 Redis TTL。
- Legacy / LangGraph 5 组输入全部等价；前端 31/31；契约重新生成无 diff；Docker API Playwright 20/20。
- GitHub Actions 三套后端 matrix、迁移、契约、前端与 Docker E2E 均已在托管环境运行；T6 冻结时为 `35333253707`（20 场景），最新为 `35409969801`（`bfcdd0e`，22 场景），均 6/6 Job 通过。

## E 一致性与可恢复性专项（已完成，2026-09-18）

本轮只做四件事：把文档口径校正到与代码一致、让意图路由不再把歧义请求直接变成动作、把澄清做成可恢复的闭环、把"重启恢复"从含糊说法变成可查询的明确语义；另外把真实设备、语音和传感器接口的字段补齐为可实现的协议。**没有**新增技术栈，**没有**接入任何真实硬件。

| 项 | 位置 | 证据 |
|---|---|---|
| 意图路由：否定语义（"我不想休息，只想关灯" → 设备指令）、设备冲突（"先开灯再关灯" → 澄清）、指代不清（"把那个调低一点" → 澄清） | `agents/orchestrator/agent.py::route_intent` | `tests/test_agents.py` 新增 3 项；澄清分支不产生计划，也不产生设备动作 |
| 澄清闭环：`conversationId` + `PendingClarification` 持久化，账户/人物/空间/会话四重隔离，10 分钟过期，可取消，补充后按原意图继续 | `contracts/models.py`、`repositories/store.py`、`sql_store.py`、`services/rest_service.py` | 同上；`tests/test_experience_agent.py` 覆盖"模型返回澄清问题时不生成计划" |
| 迁移 `0004_pending_clarifications` | `backend/alembic/versions/0004_pending_clarifications.py` | `0003 → 0004 → 0003 → 0004` 升降级各一次通过 |
| 启动恢复语义：清理崩溃遗留的执行中标记；结果未知的 `running` 步骤一律**取消**，不盲目重放；结果可查询 | `services/rest_service.py::recovery_status`、`GET /api/system/recovery` | `tests/test_recovery.py` 2 项（内存模式如实说明无跨进程恢复；PostgreSQL 模式取消而非重放） |
| 设备底座 V2 协议：`DeviceGateway`（`deviceId`、`actionId` 幂等键、`serviceEpoch`、accepted/completed/rejected/unknown 回执、错误类型、观测时间与观测值） | `adapters/protocol.py` | `tests/test_adapter_protocols.py`：可执行契约替身 + `isinstance` 校验 |
| 语音网关协议：`VoiceGateway`（`audioId`、来源、语言、说话人与空间提示、置信度、播报与取消） | `adapters/voice.py` | 同上 |
| 环境事件协议：`EnvironmentEventAdapter`（事件 ID、去重键、来源、空间、采集时间、类型与值） | `adapters/events.py` | 同上；演示用的 `POST /api/spaces/{id}/events` 仍是独立入口并标注 `simulated` |
| E：澄清路径的浏览器端到端场景（提问 → 不产生计划也不碰设备 → 补充信息后在同一会话继续 → 冲突请求再次澄清 → 否定 + 明确指令走设备分支且不起服务） | `apps/mobile/e2e/run_e2e.py::scenario_clarification` | `http-clarification`、`mock-clarification` 两个场景通过；总数 20 → 22 |
| 文档口径校正与工程评审说明 | `docs/agent-engineering-review.md`、`docs/architecture.md`（关键规则 27、28）、本文件、`AGENT-HANDOFF.md`、`docs/acceptance.md`、`docs/evidence.md` | 三档口径分开写：已实现并验证 / 接口预留 / 待下一位执行 |

### 本轮复跑的检查基线

| 组合 | 结果 |
|---|---|
| 后端 内存 + legacy | `136 passed / 19 skipped` |
| 后端 PostgreSQL + legacy | `150 passed / 5 skipped` |
| 后端 PostgreSQL + Redis + LangGraph | `154 passed / 1 skipped` |
| Alembic `0003 → 0004 → 0003 → 0004` | 通过 |
| Legacy / LangGraph 等价 | 5 组输入全部等价 |
| 前端 | `tsc --noEmit`（含 tests）无错；`32 passed` |
| 契约 | 重新生成 `openapi.json` 与 `schema.ts`，与仓库内容逐字节一致 |
| 网页端到端 | 27/27 场景通过（含澄清 2、语音 2、直接控制 3） |

### 本轮明确不做（留给下一位，需用户授权）

1. **多实例与真实部署**：虚拟 Gateway 已验证 fencing；真实网关仍须实现过期代次拒绝，并根据硬件命令时间增加 Redis 锁续租。
2. **真实后台调度器**：把模拟时钟换成可恢复的调度器，并验证时区、漏触发与重复触发。
3. **真实设备 / 语音 / 传感器接入**：实现上面三个协议并做异步回执、重复 `actionId`、过期 `serviceEpoch`、状态回读的联调。
4. **真机验收与 DeepSeek 多样本指标**：见 `docs/device-build.md`、`docs/project-metrics.md`。

## G 语音与设备直接控制（已完成，2026-09-19）

本轮做两件事：把语音从一个占位按钮做成完整回合，并把设备面板从只读改成可直接控制。
**没有接入任何真实硬件**；语音识别的原生路径代码完整但未在真机验证，见本节末尾。

### 语音

| 项 | 位置 | 证据 |
|---|---|---|
| 语音状态机：`idle → armed → listening → resolving → sending → speaking`，任一环节出错进 `failed`。只管采集，不管执行与撤销 | `apps/mobile/features/voice/machine.ts` | `tests/voice.test.ts`（17 项）。关键不变量有测试守着：**所有超时都落在 `idle` 或 `failed`，没有任何超时能走到 `sending`**——卡住的请求不会自己变成设备动作；取消后迟到的识别结果不会复活这一轮 |
| 文案集中管理：会宣称"识别"的那句由 `asrConnected` 控制 | 同上 `statusLabel()` | 同上。"有没有说假话"是一次 grep，不是逐个组件审 |
| 来源标注：点选的挂"示例指令"，手动输入挂"手动输入"，真识别出来的不挂 | `machine.ts::needsSourceBadge`、`features/chat/MessageView.tsx` | 端到端 `http-voice`、`mock-voice` 断言标签确实是"示例指令" |
| 真实 TTS：`expo-speech` 驱动系统合成器，可随时打断 | `features/voice/speech.ts` | `tests/speech.test.ts`（7 项）。两个坑已处理：`speak()` 是入队不是打断，所以每次播报前先 `stop()`；Android 没有 `pause/resume`，因此界面只提供"跳过"不提供"暂停" |
| 波形**只在接上真实识别时才画** | `features/voice/VoiceSheet.tsx` | 电平是真实音频数据。没有识别器时画假波形，视觉上与真的无法区分——等于伪造识别过程，明确不做 |
| 设备端识别适配层：`expo-speech-recognition` 57.1.0，系统自带引擎，无密钥、无费用，`supportsOnDeviceRecognition` 为真时音频不出设备 | `features/voice/deviceSpeech.ts`、`app.json` 的配置插件与权限文案 | `tests/deviceSpeech.test.ts`（12 项，用契约替身）：只转发 `isFinal` 结果、空结果算 no-match、一轮结束立即摘监听、abort 静默而真错误上报 |

### 设备直接控制

| 项 | 位置 | 证据 |
|---|---|---|
| 直接控制接口 `POST /api/spaces/{id}/devices/control`，立即执行并返回撤销窗口 | `backend/app/services/rest_service.py::control_device` | `backend/tests/test_device_control.py`（14 项） |
| 撤销 `POST /api/devices/undo/{undoId}`：反向写入记录下来的原值 | 同上 `undo_device_control` | 同上：把"关灯"撤销回 30% 而不是 100%；一次性；新写入顶替旧机会；超时/重置/代次变化都失效 |
| "直接"只是没有对话框，不是没有检查 | 同上 | 仍走同一个执行器：白名单、参数范围、代次 guard、写入、回读。被拒绝的写入不给撤销 |
| 双轨滑块：拖动中只改本地值，松手才写一次；手势被抢走回滚快照 | `apps/mobile/features/devices/control.ts`、`DeviceSlider.tsx` | `tests/deviceSlider.test.ts`（11 项）：包含吸附后不留二进制漂移、越界夹紧、三态可交互性 |
| 目标值与回读值双指示 | `DeviceSlider.tsx` | 大手柄 = 目标，小圆点 = 实测，中间高亮 = 正在弥合的差距 |
| 前端 Mock 与后端行为对齐 | `services/mock/mockApi.ts` | `tests/deviceControl.test.ts`（9 项），与后端同名用例一一对应 |

### 本轮复跑的检查基线

| 组合 | 结果 |
|---|---|
| 后端 内存 + legacy | `150 passed / 19 skipped` |
| 后端 PostgreSQL + legacy | `164 passed / 5 skipped` |
| 后端 PostgreSQL + Redis + LangGraph | `168 passed / 1 skipped` |
| 前端 | `tsc --noEmit`（含 tests）无错；`88 passed` |
| 契约 | 重新生成与仓库内容一致 |
| 网页端到端 | **27/27**（新增 `http-voice`、`mock-voice`、`http-device-control`、`mock-device-control`、`http-control-expiry`） |

### 明确的未验证项

**设备端语音识别没有在真机上跑过。** 原生模块需要 development build（Expo Go 里用不了），
云端容器和桌面 VM 都执行不了原生路径，Playwright 无头浏览器也没有麦克风——
**这条路径永远进不了自动化回归，只能人工验收**。在真机验证之前：

- 不得在任何文案、演示脚本或对外介绍里声称"语音识别""实时转写""唤醒词""声纹""置信度"。
- 顶栏的"演示模式 · 语音未接入"标识与消息气泡的来源标签不得去掉。
- 真机验收步骤：`npx expo run:ios`（或 EAS 开发版）→ 授予麦克风与语音识别权限 →
  按住麦克风说话 → 确认转写出现且**不带**来源标签 → 确认播报可被打断。
  平台门槛：iOS 17+ 完整；Android 13+ 完整；Android 12 及以下只有基础识别。

### 撤销窗口的明确语义

撤销窗口只存在于进程内。重启之后没有东西可撤销，跨实例也不提供——这是明确语义，不是遗漏。
真实设备接入后，撤销是否安全还取决于设备网关是否拒绝过期代次，见 `docs/agent-engineering-review.md`。

## F + G 合并回归（2026-09-19）

F（受控执行）与 G（语音与设备直接控制）是两条并行开展的工作，在 `c991d7f` 处分叉，
合并时有 4 处冲突（`AGENT-HANDOFF.md`、`README.md`、`contracts/models.py`、
`scripts/build_evidence.py`、生成文件 `docs/evidence.md`），均为两边各自新增内容并存，
没有语义冲突。合并后重跑的才是当前有效数字——F 与 G 各自提交里的数字都只代表合并前。

| 组合 | 结果 |
|---|---|
| 后端 内存 + legacy | `158 passed / 19 skipped` |
| 后端 PostgreSQL + legacy | `172 passed / 5 skipped` |
| 后端 PostgreSQL + Redis + LangGraph | `176 passed / 1 skipped` |
| Alembic | 空库 → `0005`；`0005 → 0004 → 0005` 升降级通过 |
| Legacy / LangGraph 等价 | 5 组输入全部等价 |
| 前端 | `tsc --noEmit`（含 tests）无错；`88 passed` |
| 契约 | 两边都改过契约，已重新生成 |
| 网页端到端 | **27/27** |

两条线在设计上不打架：F 管"Agent 凭什么能碰设备"（策略决定 → 有界授权 → 动作账本 →
Gateway），G 管"人怎么碰设备、碰错了怎么收回"（语音回合、直接控制、撤销窗口）。
合并后设备写入路径仍然只有一条。

**F 与 G 合并后都还没有在 GitHub Actions 上跑过。** 上一次绿灯是 E 专项基线
（运行 `35409969801`，对应 `bfcdd0e`），不能用它声称当前改动已经过托管验证。

## 本地冻结后仍待完成

A 真机验收（有 iPad 时） · D 的设备部分（EAS 开发版构建、平板录屏） · 旧 HTML 前端清单（用户尚未提供旧文件） · E 专项列出的四项"明确不做"（多实例与真实部署、真实调度器、真实设备/语音/传感器接入、多样本模型指标）

## 下一步接口

- 设备侧验收：有 iPad 或安卓平板时完成真机构建与录屏。
- 若以后换成真实定时器：由定时器调用 `advance_clock`，认领与守卫逻辑不变；但必须先补齐时区、漏触发与重复触发的验证。
- 若以后接真实设备：以真实实现替换 `AdapterDeviceGateway`，不改 `DeviceGateway` 契约与授权链；`GET /api/system/recovery` 的 `deviceStateReconciled` 只有在真实回读对齐后才允许改成 `true`。

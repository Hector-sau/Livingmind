# LivingMind AI 交接文档

更新日期：2026-09-18
仓库位置：`/Users/macbookair/Desktop/Business/项目材料整理/Livingmind/livingmind-app/`  
当前分支：`main`  
第一批实现基线提交：`99b1138 feat: step 4 rule-based backend loop, executor, virtual devices, CI`  
演示稳定基线：`5cd8eeb fix: freeze stable demo lifecycle`
当前基线：演示主链路、1+2 Agent、整晚服务、能源快照、稳定性收尾以及 **T1–T6 本地工程化冻结均已完成**。Docker Compose 全栈、Worker 事件链、迁移升降、三套后端组合与 Docker API Playwright 20/20 已在用户 Mac 验证。方案见 `docs/technology-architecture.md`，逐项证据见 `docs/status.md`。

## 0. 项目背景与现状速览（给评审或新接手的 AI）

### 0.1 背景

- **项目**：LivingMind，参加 SpaceMind AI Agent 创新应用大赛，已进入复赛，需要约 8 分钟汇报 + 可演示原型。对外品牌和代码命名统一用 LivingMind；旧名称不再使用。
- **定位**：家庭住宅（Home Living）为核心场景，酒店（Smart Stay）为延展；两者共享 Energy Intelligence。叙事核心：“一次表达，持续服务；体验是约束，能源是优化”。
- **目标架构**（汇报口径）：主 Agent + 两个专业 Agent（Experience、Space Execution）+ 共享 Memory + Harness；SpaceMind 为“拟对接能力”，具体接口待官方文档与联调确认。
- **团队约束**：学生团队，出发点是“演示有原型支持、简历有技术可讲”。深度标准：**演示可见、面试可答、代码可指**，够用即停。
- **数据约定（用户已确认）**：测试与演示数据用设计的模拟数据即可，重点是讲清方案与验证方法、体现测试意识；数据设计见 `docs/test-data.md`。真实模型的多次统计是可选项。
- **相关材料**：`docs/technology-architecture.md` 是当前仓库的工程化升级设计与技术上手指南；`docs/project-metrics.md` 说明每项技术解决的问题、指标公式、现有证据、DeepSeek 多轮评测和前后对比方法；`../汇报演示/LivingMind_presentationV1.pdf`（10 页）和 `../架构评审/LivingMind-架构评审与迁移步骤-v0.2.md` 只作只读背景，不是执行授权。

### 0.2 已完成（有代码、有测试、有提交）

| 项 | 内容 | 证据 |
|---|---|---|
| 步骤 0–1 | 仓库骨架、文档基线、Expo SDK 57 App、FastAPI 健康检查、平板配置、可配置后端地址 | `c4e8d9b`、`19599db` |
| 步骤 2 | Pydantic 契约 → OpenAPI → TS 类型自动生成；统一错误格式；两个种子人物偏好不同 | `386bc2e`，`tests/test_contracts.py`、`test_seed.py` |
| 步骤 3 | 可点击原型：人物 → 需求 → 计划 → 确认 → 设备 → 停止 → 动态；平板/手机响应式；前端 Mock 与后端规则一致 | `e8ffb61`，`apps/mobile/tests/` |
| 步骤 4 | 固定规则、统一执行器（白名单、范围、每动作前重查）、有状态虚拟设备、服务状态、幂等确认、停止失效、计划过期、活动记录、PR 模板 + CI | `99b1138`，`tests/test_rest_flow.py`（7 项验收） |
| B | 设备写入移出服务锁；停止可中途抢占慢设备批次（服务层 + HTTP 层测试） | `c639d5d`，`tests/test_concurrency.py` |
| ⑤ | Experience Agent：DeepSeek Provider、Pydantic 输出校验、规则/模型开关、六类失败降级为规则并标注、App 四种来源标签；真实调用已验证（deepseek-flash，2035 ms，单次） | `469dc9a`、`2ad87da`，`tests/test_experience_agent.py` |
| R1 评审修正 | 模型偏离上限（后端强制）、兜底异常、App 计划超时联动、过期提示刷新、`demo_reset` 记录、模拟模式措辞、PR 模板 Mock 同步项、`.env` 格式提示、**网页端到端脚本入库**；真实模型端到端脚本（`backend/scripts/e2e_real_model.py`、`run_e2e.py --real-model`） | 见 `git log`，`apps/mobile/e2e/` |
| ⑧ | 主 Agent（规则路由 + 编排 + 协作轨迹）、Space Execution Agent（设备能力、空间规则、指令解析）、人物记忆（本人偏好读取与编辑、空间规则、共享列表不含偏好）、能源智能（舒适范围、分时电价、估算档位、舒适优先 / 节能模式）、Harness 预检；设备指令简化分支；计划卡“查看协作过程” | `backend/tests/test_agents.py`（33 项）、`apps/mobile/tests/agents.test.ts`；端到端 `mock-agents`、`http-agents`、`http-energy-memory` |
| C | 天蓝色明亮主题（用户指定）、LivingMind Logo（头部 / App 图标 / 启动图 / AI 头像）、`@expo/vector-icons` 图标、渐变按钮、柔和阴影、入场 / 呼吸 / 数值条动画（React Native `Animated`，尊重减弱动态效果）、骨架屏 | 端到端 12/12 |
| ⑥b | 四个入口（对话 / 空间 / 场景 / 我的）；对话主页（计划卡、结果卡、系统消息、服务状态条、语音占位）；演示 PIN 切换与访客模式；只显示本人偏好；证据面板；场景库；数据重新设计（3 位成员 + 访客、15 条评测用例） | `tests/test_people_and_scenes.py`、`tests/test_eval_cases.py`、`apps/mobile/tests/conversation.test.ts`；端到端 12 个场景 |
| ⑥ | 模拟室温事件 → 一次自动调整：事件接口、冷却 30 秒、上限 3 次、单服务单调整、停止后忽略、规则调整（±1°C，偏好 ±3°C 内）、模型调整跟随服务模式并受偏离上限约束；App 注入按钮与调整次数；Mock 同步 | `backend/tests/test_events.py`（10 项）；端到端 `mock-event`、`http-event` |
| ⑨ | 一键“准备演示”（重置 → 林悦 · 舒适优先 · 设备 80/26/100 · 清空对话 · 关证据面板 · 回对话页）；“场景”页“1+2 Agent 如何协作”说明卡（有计划时展示真实协作过程）；信息提示 3 秒淡出；空态大图标；README 演示启动命令；`docs/demo-script.md` 3 分钟讲稿 | `apps/mobile/tests/notices.test.ts`；端到端 `http-prepare-demo` |
| ⑦ | 整晚服务：休息计划附带 5 步整晚安排（Space Execution Agent 规则生成、Harness 预检、随计划确认）；模拟时钟推进接口 `POST /api/services/{id}/clock/advance`；每步最多执行一次（锁内认领 + 单服务单推进）；停止取消剩余步骤；只有每步全部设备动作成功才 `completed`；App 运行条“模拟已入睡 / 快进 / 自动播放整晚”、计划卡整晚安排、空间页整晚时间线、场景“起床渐进唤醒”改为已实现 | `backend/tests/test_night_service.py`（15 项）、`apps/mobile/tests/night.test.ts`；端到端 `http-night`、`mock-night`、`http-night-stop-phone` |
| 稳定性与接口预留 | 自动时钟与环境调整互斥；调整等待时仍可停止且迟到响应不回写；重置通过服务代次和设备代次隔离旧任务；设备回读异常结果化；模拟入睡、三档起床时间；真实设备 / 语音协议预留；能源研究绘图使用迁入后的权重路径 | 后端 115 项测试；端到端 `http-stop-during-event`；`adapters/protocol.py`、`adapters/voice.py`、`docs/team-workflow.md`、`docs/demo-freeze.md` |
| D（云端） | 三段网页版录屏脚本；主张证据表（28 条，Markdown + 5 页 PDF）；`eas.json` 开发版配置、平板安装与真机验收清单 | `apps/mobile/e2e/record_demo.py`、`scripts/build_evidence.py`、`docs/evidence.md`、`docs/device-build.md` |
| 工程化升级 | 明确并实现 LangGraph、PostgreSQL、Redis、数据库 Outbox 事件总线与 Docker 的职责、边界和关键数据流；表结构、Redis Key、并发语义与验收证据均有对应代码 | `docs/technology-architecture.md`、`docs/status.md` |
| 项目指标指南 | 聚焦面试最常见的响应效率、Redis缓存、稳定性规模与能源效果；提供DeepSeek 45次延迟基线和Redis缓存前后对比方案，其他模块以机制与测试事实说明；**尚未运行新的性能评测** | `docs/project-metrics.md` |
| T1 Docker 基线 | 后端镜像（Python 3.12、多阶段、非root、依赖锁）、可配置宿主端口、能源JSON只读挂载、失败自动清理的`verify-t1.sh` | 用户Mac实测：镜像构建；127通过/18跳过；PostgreSQL迁移；Redis/API healthy；用户`livingmind`；镜像无`.env`；宿主机休息闭环通过；镜像96,471,430 bytes |
| T2 PostgreSQL 持久化 | 同步栈 SQLAlchemy 2 + psycopg3 + Alembic；`Store` 协议 + 内存/SQL 两种实现（都返回副本，强制“改完必须存”）；偏好、计划、服务、整晚步骤、动作结果、活动记录、空间代次、进行中标记全部落库；数据库约束：每空间一个 active 服务（部分唯一索引）、夜间步骤 `UPDATE … WHERE status='pending' RETURNING` 只认领一次 | 同一套测试换存储再跑一遍（`LIVINGMIND_TEST_STORE=sql`）；重启恢复、并发认领、绕过服务层插入第二个 active 被数据库拒绝；网页端到端在两种存储下各 20/20 |
| T3 LangGraph 规划图 | 编排器拆成阶段方法，legacy 与 graph 共用同一批方法；`StateGraph` 路由 + 四分支；依赖不进状态因此 checkpoint 可序列化；`LIVINGMIND_ORCHESTRATOR=legacy\|langgraph`；等价定义与对照脚本 | `LIVINGMIND_ORCHESTRATOR=langgraph` 下整套测试通过；`scripts/compare_orchestrators.py` 5 组输入全部等价；配数据库时 `PostgresSaver` 自建 checkpoint 表 |
| T4 Redis 协调 | 空间执行锁（随机 token + 30 秒 TTL + Lua 校验释放）、事件冷却快速判断；未配置或连不上自动退化 | 唯一持有者、别人的锁不误删、TTL、第二实例收到 `SPACE_BUSY`、删掉冷却键也绕不过规则、Redis 连不上主流程照常 |
| T5 Outbox 与事件总线 | 事件信封；业务事实与 outbox 同事务；publisher（SKIP LOCKED / 重试 / 死信不删）；consumer（`consumer_receipts` 去重 → `service_projection`）；总线默认是 PostgreSQL 表 | `tests/test_outbox_events.py`：同事务提交、回滚不留事件、至少一次且不重复、总线停摆不挡设备、重复投递靠回执保护、同空间保序 |
| T6 本地集成冻结 | Compose 全栈、Worker 投递消费、迁移升降、三套后端 matrix、Docker API E2E、证据表和最终文档 | 127/141/145 后端组合；Outbox 7/7；Worker 重启无重复；Playwright 20/20；契约无 diff；PDF 逐页检查 |
| 文档 | 本交接文档、README、architecture、acceptance、status、ui-polish；产品界面方向（第 12 节） | `587d7aa`、`8525718`、`c58a29f` |

检查基线（数量以`docs/status.md`为准）：默认后端127通过/18跳过；PostgreSQL+legacy 141通过/4跳过；PostgreSQL+Redis+LangGraph 145通过；前端31项+类型检查；Legacy/LangGraph 5组等价；Docker API网页端到端20/20；契约无diff。Compose两个Worker常驻验证已完成。GitHub Actions 托管 CI 运行 `35333253707` 的 6 个 Job 全部通过。尚未执行：真机安装；iOS/Android JS与Hermes导出成功。

### 0.3 当前状态与外部待办

| 项 | 状态 | 说明 |
|---|---|---|
| T1 Docker 基线 | **已完成并通过宿主机验证** | Docker 29.6.2 / Compose 5.3.1；完整证据见`docs/status.md`与本机`dist/t1-verify.log` |
| T2 PostgreSQL 持久化 | **已完成（单实例）** | 跨实例并发靠 T4 的锁 + 数据库约束；设备状态仍在内存虚拟适配器里（模拟硬件，不是业务事实） |
| T3 LangGraph 规划图 | **已完成（规划分支）** | 事件调整仍走 legacy 单阶段；图不执行设备 |
| T4 Redis 协调 | **已完成** | 未做设备状态缓存与幂等结果缓存，原因见 `docs/status.md` |
| T5 Outbox + 事件总线 | **已完成（数据库队列实现）** | Kafka 实现按用户决定不写：没有 broker 可验证；接口留在 `EventPublisher` |
| T6 集成与冻结 | **已完成** | 本地完整回归与 GitHub Actions 6/6 均通过；真机属于单独的设备验收 |
| A 真机验收 | 未做 | 用户暂无 iPad；所有界面验证来自网页版，不能替代真机 |
| 真实模型的多次延迟统计 | 已规划、未执行 | 用户已同意后续多次调用并做响应效率优化前后对比；当前仍只有2035 ms单次样本。方法和结果模板见 `docs/project-metrics.md`，不为每个模块制造百分比 |
| C 视觉整理 | 已完成 | 未做项见 `docs/ui-polish.md` 顶部 |
| ⑦ 整晚服务 | **已完成** | 模拟时钟，由按钮或自动播放推进；不是真实定时器 |
| ⑧ 主 Agent / 执行 Agent / 记忆 / 能源规则 | **已完成** | 如何如实描述见 0.4 |
| ⑨ 演示打磨 | **已完成** | 旧 HTML 清单未做（用户未提供旧页面） |
| D 演示打包 | **云端部分已完成** | 网页版录屏 3 段、主张证据表（`docs/evidence.md`）、开发版配置与安装说明（`docs/device-build.md`）；EAS 构建与平板录屏待设备 |
| P07 能源仿真证据 | **已迁入（离线展示）** | `simulation/home-energy/` 保存给定研究快照、结果与溯源；App 通过只读 API 展示固定日结果，不重训、不重新评估、不参与控制 |
| GitHub 远程与 CI 实跑 | **已完成** | `origin=https://github.com/Hector-sau/Livingmind.git`；运行 `35333253707` 为 6/6 通过 |

### 0.4 评审时最该核对的五个点

1. **声明与实现是否一致**：`docs/status.md` 每一行是否能在代码和测试里找到对应。⑧ 之后“1+2 Agent 编排”已实现，如实描述应为：
   - 主 Agent：**规则**路由与编排，记录每一步协作轨迹；
   - Experience Agent：**可调用大模型**（DeepSeek），结构化输出、校验、偏离上限、失败降级；
   - Space Execution Agent：**规则**实现的能力感知动作规划与中文设备指令解析；
   - 共享人物记忆、能源规则（舒适范围内的分时电价建议，负荷为规则估算）、Harness（预检 + 执行前 guard）。
   不要说成“三个大模型 Agent”，也不要把能源规则说成 MATD3 在线控制。
2. **来源标注是否可能被混淆**：前端模拟 / 规则 / 模型 / 规则降级 / 虚拟设备在界面和活动记录里是否始终可区分。
3. **安全边界**：所有设备写入是否都经过 `harness/executor.py`；模型输出是否先过 Pydantic 再进执行器；密钥是否只在后端 `.env`。
4. **并发语义**：停止后是否确实不再有新动作；已开始的单个动作不撤销是否可接受。
5. **范围控制**：后续步骤是否仍遵守“一次一步、达到即停”，没有空目录或类名冒充能力。

### 0.5 评审 AI 的复现命令

```bash
cd livingmind-app
git log --oneline                       # 提交按步骤拆分
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt && pytest
cd ../apps/mobile && npm install && npm run typecheck && npm test
cd ../.. && ./scripts/gen-api.sh && git diff --exit-code -- packages/api-client
# 可选：网页端到端（需 pip install -r apps/mobile/e2e/requirements.txt && python -m playwright install chromium）
python apps/mobile/e2e/run_e2e.py
# 仅在有密钥的机器上：真实模型端到端
cd backend && set -a && source .env && set +a && .venv/bin/python scripts/e2e_real_model.py
```

评审 AI 只读不改；发现问题写成清单交给用户，不直接修改代码或本文件。

## 1. 接手结论

第一批步骤 0–4、B 并发修正、⑤ Experience Agent（含一次真实 DeepSeek 调用验证）、R1 评审修正、⑥ 一次事件调整、⑥b 对话外壳、C 视觉整理、⑧ 补齐模块、⑨ 演示打磨和⑦ 整晚服务已完成。用户目前没有 iPad，真机验收（A）推迟到有设备时。

用户已确认在**不重写现有演示链路**的前提下，把项目演进为 Docker → PostgreSQL → LangGraph → Redis → Outbox + 事件总线 → 集成冻结。T1–T6 本地阶段均已完成，详细职责和验收见`docs/technology-architecture.md`。下一位Agent不应继续扩展基础设施；只在用户授权远程仓库或提供平板时执行外部验收。

当前产品是一条可工作的纵向链路，规划阶段可选规则或模型：

```text
Expo App：对话 / 空间 / 场景 / 我的（计划来源开关：规则 / 模型；演示 PIN 切换人物或访客）
  → 可切换的前端 Mock / HTTP API
  → FastAPI：POST /api/assistant/messages
  → 主 Agent（规则路由）
      休息请求：人物记忆 → Experience Agent（规则或 DeepSeek，失败降级）→ 能源智能 → Space Execution Agent → Harness 预检
      设备指令：Space Execution Agent 解析 → Harness 预检
      状态查询 / 其他：直接回答
    （只生成计划，不改设备；等待模型时不持锁；计划附协作轨迹）
  → 用户确认
  → 统一执行器（白名单、参数、服务状态检查）
  → 有状态虚拟灯光 / 空调 / 窗帘
  → 状态回读与活动记录
  → App 更新

服务运行中：模拟入睡 → 首个夜间步骤；模拟室温事件 → 检查（服务 / 自动操作互斥 / 上限 / 冷却）→ 规划调整（跟随服务模式）
  → 同一执行器 → 回读 → 记录；停止后事件一律忽略。夜间时钟与环境调整不会并发写设备。
```

场景范围只有 Home Living 的“我想休息”。**当前实现**仍没有持久化数据库、LangGraph、Redis、事件总线、真实认证、真实传感器、SpaceMind 或真实设备接入；事件只有模拟室温一种；在线能源建议是规则，MATD3 仅作为固定日的只读离线仿真展示。模型调用已用真实 DeepSeek 密钥验证过一次（deepseek-flash，2035 ms）；延迟为单次样本。

**目标实现**使用 PostgreSQL 保存业务事实、人物记忆与 LangGraph checkpoint；Redis 负责短期协调与缓存；Transactional Outbox 把领域事件异步分发到事件总线（默认 PostgreSQL 队列实现，Kafka 可选）；Docker Compose 提供可复现的后端开发环境。后端保持同步技术栈，异步化另立项目。LangGraph 只编排规划，不允许节点绕过 Harness / Executor 直接操作设备。

## 2. 接手后的必读顺序

0. 第 0 节：背景、已完成/未完成、评审要点（评审 AI 读到这里即可开始）。
1. 本文件其余部分：边界和下一任务。
2. `README.md`：启动方法和三条架构边界。
3. `docs/technology-architecture.md`：工程化目标、每项技术的真实用途、数据设计、故障降级和 T1–T6 验收。
4. `docs/project-metrics.md`：现有指标证据、未来补测方法、前后对比模板与简历口径。
5. `docs/status.md`：已实现、证据、未实现内容。
6. `docs/acceptance.md`：每阶段达到什么程度就停止。
7. `docs/architecture.md`：当前代码链路和目录职责。
8. 第 12 节：产品界面方向，执行 ⑥b、C、⑨ 前必读。
9. `docs/ui-polish.md`：视觉整理清单，执行 C 时必读。
10. `docs/test-data.md`：演示与测试数据的设计。
11. 修改 `apps/mobile/` 前阅读 `apps/mobile/AGENTS.md`，并查看其要求的 Expo SDK 57 版本文档。

不得把架构评审、PDF 或演讲稿中的描述直接当成“代码已经实现”。以仓库、测试和 `docs/status.md` 为准。

## 3. 不可破坏的架构边界

1. **页面不直接控制设备。** 页面只依赖 `apps/mobile/services/api.ts`；Mock 和 HTTP 实现遵循相同接口。
2. **Agent 不绕过执行器。** 规则计划和未来模型计划都必须进入 `backend/app/harness/executor.py`，经过检查、设备写入和回读。
3. **模拟逻辑集中存放。** 前端模拟在 `apps/mobile/services/mock/`，虚拟设备在 `backend/app/adapters/virtual/`，种子数据在 `backend/app/demo/`。
4. **后端契约是唯一类型来源。** 修改 `backend/app/contracts/` 后必须运行 `./scripts/gen-api.sh`；不要手改生成的 `packages/api-client/src/schema.ts`。
5. **所有来源必须如实标记。** `frontend_mock`、`rule`、未来的 `model` 和规则降级不能混写，不能伪造模型或设备调用轨迹。
6. **演示身份不等于认证。** 当前服务只能在本机或可信局域网运行，不得部署到公网。

统一深度标准：**演示可见、面试可答、代码可指。** 每个模块只做一条真实工作路径和相关关键失败路径，达到 `docs/acceptance.md` 后停止扩展。

## 4. 已实现内容

| 步骤 | 已完成内容 | 主要位置 |
|---|---|---|
| 0 实施基线 | 项目说明、架构、验收与状态文档 | `README.md`、`docs/` |
| 1 最小骨架 | Expo SDK 57 原生 App、平板配置、FastAPI 健康检查、可配置后端地址 | `apps/mobile/`、`backend/app/main.py` |
| 2 数据契约 | Pydantic 契约、统一错误、OpenAPI → TypeScript 类型、两个种子人物 | `backend/app/contracts/`、`packages/api-client/`、`scripts/gen-api.sh` |
| 3 可点击原型 | 人物 → 需求 → 计划 → 确认 → 设备 → 停止 → 活动；平板/手机响应式布局 | `apps/mobile/features/`、`apps/mobile/services/mock/` |
| 4 无模型后端链路 | 固定规则、统一执行器、有状态虚拟设备、状态回读、活动记录、PR 模板与 CI | `backend/app/rules/`、`harness/`、`services/`、`adapters/virtual/`、`.github/` |
| B 并发修正 | 设备写入移出服务锁；每个动作前在锁内重查服务与代次；慢设备抢占测试（服务层 + HTTP 层） | `backend/app/services/rest_service.py`、`tests/test_concurrency.py` |
| ⑤ 最小 AI 证据 | Experience Agent（提示词、Pydantic 输出校验、DeepSeek Provider）、规则/模型切换、降级标注、延迟记录、App 来源开关与四种来源标签、`scripts/try_model.py` | `backend/app/agents/experience/`、`services/planner.py`、`apps/mobile/features/rest/ModeToggle.tsx` |
| R1 评审修正 | 偏离上限、兜底异常、超时联动、端到端脚本入库、真实模型端到端脚本 | `services/planner.py`、`api/errors.py`、`apps/mobile/e2e/`、`backend/scripts/e2e_real_model.py` |
| ⑧ 补齐模块 | 主 Agent、Space Execution Agent、人物记忆、能源智能、Harness 预检、协作过程展示、偏好编辑、节能模式 | `backend/app/agents/orchestrator|space_execution/`、`memory/`、`energy/`、`harness/policy.py`；`apps/mobile/features/agents/`、`energy/`、`me/`、`space/` |
| ⑥b 对话外壳 | 四入口外壳、对话流、我的页（PIN / 访客 / 证据面板）、空间与场景简版、演示数据与评测集 | `apps/mobile/features/shell|chat|me|space|scenes/`、`backend/app/demo/seed.py`、`backend/evals/`、`app/agents/experience/evaluation.py` |
| ⑦ 整晚服务 | 整晚安排规则、模拟时钟推进、单次执行、停止取消、服务完成；App 快进与自动播放、整晚时间线 | `backend/app/rules/night_rule.py`、`agents/space_execution/agent.py::night_schedule`、`services/rest_service.py::advance_clock`；`apps/mobile/features/night/` |
| ⑨ 演示打磨 | 准备演示按钮、协作说明卡、提示淡出、空态、演示讲稿 | `apps/mobile/features/shell/AppShell.tsx`、`notices.ts`、`features/scenes/ScenesScreen.tsx`、`components/EmptyState.tsx`、`docs/demo-script.md` |
| ⑥ 一次事件调整 | 事件接口、检查顺序、调整规则、模型调整、App 注入按钮 | `services/rest_service.py::inject_event`、`rules/rest_rule.py::adjustment_rule`、`services/planner.py::plan_adjustment`、`apps/mobile/features/rest/ServiceCard.tsx` |

当前 Git 提交按步骤拆分：

```text
c4e8d9b docs: step 0 implementation baseline
19599db feat: step 1 minimal Expo app and FastAPI skeleton
386bc2e feat: step 2 data contracts, unified errors, generated API types
e8ffb61 feat: step 3 clickable rest-flow prototype with front-end mock
99b1138 feat: step 4 rule-based backend loop, executor, virtual devices, CI
```

仓库当前没有远程地址，没有推送或发布。

## 5. 当前强制业务语义

以下规则由后端执行，不只依赖 UI：

- 创建计划不改变设备，只有确认后执行。
- 同一计划重复确认不重复写设备。
- 同一空间只允许一个活跃休息服务。
- 计划 10 分钟后过期，身份、人物、空间、计划版本不符会被拒绝。
- 停止后，空间此前未执行的计划失效；已执行计划不能重新启动服务。
- 停止后设备保持当前状态，不自动恢复。
- 每个设备动作经过白名单、参数范围检查、写入和回读。
- API 不可达时，App 显示失败和状态可能过期，不偷偷回退到 Mock 成功。
- 数据仅在进程内存中保存，后端重启或演示重置会清空。
- 模拟事件只作用于正在运行的服务；没有服务、上一次调整未结束、达到 3 次上限、30 秒冷却中都会忽略并写明原因；停止后事件一律忽略。
- 同一服务的自动操作互斥：夜间步骤执行中，环境事件忽略；环境调整中，时钟不推进。停止期间开始的慢规划返回后，计划必须是 `invalidated`，不能重新启动服务。
- 夜间步骤任一设备动作失败、被拒绝或被跳过时，该步取消且服务最终为 `failed`；仅全部设备动作成功才完成。
- “模拟已入睡”是明确演示事件，不是传感器；起床时间只允许 06:30 / 07:00 / 07:30。
- 事件调整跟随服务的计划模式；只对有变化的设备生成动作；调整次数在执行前计数。
- 演示 PIN 只防误切换：不签发令牌，后续请求不据此授权，任何接口都不返回 PIN。访客使用空间默认设置。
- 设备指令确认后执行，不创建休息服务；停止服务会让未确认的设备指令失效。
- 共享列表不含任何人的偏好；能源“舒适优先”只建议，“节能模式”才在舒适范围内改设定。

主要接口：

```text
GET  /health
GET  /api/bootstrap
GET  /api/scenes                        # 场景库（状态如实）
GET  /api/spaces/{spaceId}/energy/simulation  # 给定的固定日离线仿真证据；只读、不参与设备控制
POST /api/assistant/messages            # 主 Agent 入口：计划或回答（附协作轨迹）
GET  /api/memory                        # 本人偏好 + 空间规则
PUT  /api/memory/preference             # 编辑本人偏好（访客不可）
PUT  /api/spaces/{spaceId}/energy-mode  # 舒适优先 / 节能模式
POST /api/persons/{personId}/unlock     # 演示 PIN，不是认证
GET  /api/spaces/{spaceId}/devices
POST /api/plans/rest
POST /api/plans/{planId}/confirm
POST /api/services/{serviceId}/stop
POST /api/services/{serviceId}/clock/advance  # 模拟时钟推进整晚安排（minutes 为空 = 下一步）
POST /api/services/{serviceId}/sleep          # 明确的模拟入睡信号，不是传感器
POST /api/spaces/{spaceId}/events      # 模拟环境事件（source=simulated）
GET  /api/spaces/{spaceId}/activity
POST /api/demo/reset
```

FastAPI 运行后可在 `http://localhost:8000/docs` 查看实时 OpenAPI 文档。

## 6. 启动与验证

要求 Node.js 20+、Python 3.10+。

### 后端

```bash
cd /Users/macbookair/Desktop/Business/项目材料整理/Livingmind/livingmind-app/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# 启用模型模式：cp .env.example .env，填 DEEPSEEK_API_KEY，再加 --env-file .env
```

验证一次真实模型调用：`set -a && source .env && set +a && .venv/bin/python scripts/try_model.py "我想休息，有点热"`

### App

```bash
cd /Users/macbookair/Desktop/Business/项目材料整理/Livingmind/livingmind-app/apps/mobile
npm install
cp .env.example .env
npx expo start
```

- `EXPO_PUBLIC_API_BASE_URL` 留空：前端 Mock 模式。
- 设置为 `http://<Mac 局域网 IP>:8000`：真实后端模式。
- 平板不能使用 `localhost` 访问 Mac；可用 `ipconfig getifaddr en0` 查询常见 Wi-Fi 地址。
- 修改 `.env` 后用 `npx expo start --clear` 重启。

### 提交前必须运行

```bash
cd backend && pytest
cd ../apps/mobile && npm run typecheck && npm test
cd ../..
./scripts/gen-api.sh
git diff --exit-code -- packages/api-client
python apps/mobile/e2e/run_e2e.py   # 改了界面或流程时
git status --short
```

上一轮记录：后端 96 项测试通过，前端 23 项逻辑测试与类型检查通过，干净副本 CI 模拟通过，网页端到端 15/15。网页版在 1180×820 和 390×844 下完成 Mock / 后端流程；断开后端时错误状态符合预期。接手 AI 不应只引用该记录，改动后必须重新运行相关检查。

## 7. 尚未验证与已知限制

- 尚未在 iPad、Android 平板、手机真机或 iOS 模拟器运行；网页预览不能替代真机验收。
- GitHub Actions 已真实运行；`main@197037a` 对应运行 `35333253707` 的 6 个 Job 全部通过，包括 Docker API 浏览器端到端 20/20。
- 规则模式下用户文字只记录，固定规则不会理解任意自然语言；模型模式已验证一次真实调用（见下）。
- 没有真实身份认证、持久化数据库、WebSocket、语音、睡眠传感器或厂商设备。
- 前端 Mock 和后端内存数据互不共享；切换模式应视为不同演示环境。
- 停止不会把灯光、温度、窗帘恢复到执行前状态，这是当前明确语义。
- 计划确认即标 `executed`（已采纳），真实结果看 `results`；同一账户下任何人物都能停止服务（有意设计）。详见 `docs/architecture.md` 关键规则 10–14。
- 模型计划偏离本人偏好超过上限（灯光/窗帘 ±40、空调 ±3°C）会被后端拒绝并降级为规则。
- 网页端到端的模型路径连的是本地桩 `apps/mobile/e2e/fake_deepseek.py`，不是 DeepSeek；CI 目前不跑端到端。
- 事件没有真实传感器：室温由 App 按钮（当前设定 +3°C）或 API 直接给出，界面与记录都标“模拟事件”。
- 语音按钮是占位。Logo 为 PNG（来自旧 PPT 品牌目录，用户已同意使用），正式发布前需 SVG 母版与商标检索。
- 对话记录只在前端内存，刷新即清空。
- 主 Agent 路由与指令解析是规则；能源负荷是规则估算；室外温度与电价时段是模拟值（`LIVINGMIND_DEMO_LOCAL_HOUR` 可固定演示时段）。
- 偏好编辑与节能模式只在内存中，重置或重启即恢复。

### 并发（B 已修正）

`confirm_plan()` 现在只在锁内做记账，设备批次在锁外执行；guard 在每个动作前于锁内重查 `service.status` 与空间代次。`tests/test_concurrency.py` 用一个会阻塞首个写入的慢设备证明：停止请求立即返回，已开始的动作完成，其余跳过。已开始的那一个动作不会被撤销，这是当前语义。模型调用同样在锁外进行。

### ⑤ 的验证范围

`tests/test_experience_agent.py` 全部使用测试替身。真实调用已由用户在 Mac 上用 `backend/scripts/try_model.py` 验证一次（deepseek-flash，2035 ms，输出合法）。这是单次样本：8 秒目标在 Agent 层满足。多次统计与端到端计时的脚本已入库（`backend/scripts/e2e_real_model.py [--eval]`、`apps/mobile/e2e/run_e2e.py --real-model`），并已用本地桩空跑通过。用户已批准后续按 `docs/project-metrics.md` 建立45次真实调用延迟基线并做响应效率前后对比，但本轮没有运行。指标重点是P50/P95、降级次数与规则快速路径，不为每个模块制造百分比。注意：开发用的云端环境和 Mac 上的沙箱都无法访问 `api.deepseek.com`，真实模型只能在用户 Mac 的终端里跑。密钥只在用户本机 `backend/.env`，仓库和对话中都不应出现。

## 8. 后续执行顺序

一次只做一步，完成验收后停止并报告。T1–T6 是本轮确认的工程化升级；原字母项和⑤–⑨ 保留为演示阶段历史与待办。

### 8.1 T 系列工程化升级（用户已确认目标架构）

| 顺序 | 内容 | 达到即停 | 关键边界 |
|---|---|---|---|
| T1 Docker 基线 | FastAPI Dockerfile、`.dockerignore`、依赖版本锁定、Compose API 服务（端口绑 `127.0.0.1`）、健康检查与容器内测试 | 全新容器可启动 API；基线测试在容器内全部通过；Expo 仍能连通；端到端默认路径不变 | 本阶段不添加未被代码使用的 PostgreSQL / Redis / 事件总线 |
| T2 PostgreSQL 持久化 | Compose 加 PostgreSQL；SQLAlchemy 2.x、Alembic、Repository / Unit of Work；迁移人物记忆、计划、服务、动作、活动和 Outbox 表 | 重启后数据存在；失败事务不留半个服务；并发确认只有一个成功 | PostgreSQL 是业务事实来源；保留内存 Repository 供快速单元测试 |
| T3 LangGraph 规划图 | 用节点包装既有 Memory、Experience、Energy、Space Execution、Harness；接 PostgreSQL checkpointer | legacy / graph 对相同输入生成等价 Plan；checkpoint 可恢复；节点轨迹可见 | `LIVINGMIND_ORCHESTRATOR=legacy|langgraph`；Graph 不执行设备副作用 |
| T4 Redis 协调 | 空间短锁、冷却、短期幂等与缓存；断连降级 | 多 API 实例同一空间仍只有一个 active service；Redis 停止后核心链路可走 PostgreSQL | Redis 不是事实来源，锁必须有 token 与 TTL，数据库约束是最终防线 |
| T5 Outbox + 事件总线 | `EventPublisher` 协议、Outbox Publisher、PostgreSQL 队列实现、领域事件 envelope、首个真实 `activity-projector` Consumer、死信和幂等消费；Kafka 为可选实现与可选 profile | 总线停摆不阻断设备执行；恢复后补发；重复事件不产生重复活动；活动记录始终由同步写入保证 | 事件只传播事实，不发送设备控制命令；按 `spaceId` 保序；默认不启动常驻中间件 |
| T6 集成与冻结 | Compose 全栈、迁移与健康检查、CI 集成测试、Playwright 和真机回归、证据更新 | 一键启动；失败场景均有测试；只有实际跑过的能力写“已实现” | 不新增业务范围，集中消除集成缺陷 |

严格顺序：**T1 → T2 → T3 → T4 → T5 → T6**。每阶段保留当前演示路径；新增组件必须有一条真实工作路径、故障测试和可观察证据，不能只添加依赖、容器或空目录。

### 8.2 演示阶段历史与待办

| 顺序 | 内容 | 达到即停 | 备注 |
|---|---|---|---|
| A 真机验收 | iPad（及安卓平板，如有）用 Expo Go 跑 Mock 与后端两种模式 | 完整流程走通，问题记录到 `docs/status.md` | **推迟**：用户暂无 iPad；有设备时立即补做，期间状态保持“真机未验证” |
| B 并发修正 | 缩短 `confirm_plan` 持锁范围；每次外部写入前按 `serviceId + epoch` 重查；补慢设备/延迟 Adapter 测试 | 停止请求能中途打断慢设备批次 | **已完成**（`c639d5d`） |
| ⑤ 最小 AI 证据 | Experience Agent 一次真实模型调用；规则/模型开关；超时或非法输出降级并标注来源 | 提交到显示计划 8 秒内（待验证目标）；第 9 节测试全部通过 | **已完成**（`469dc9a`）；真实调用已验证 2035 ms（单次） |
| ⑥ 一次事件调整 | 注入一次模拟入睡或室温事件，触发一次调整；验证停止 | 休息 → 事件 → 调整 → 停止；停止后再注入不执行 | **已完成**；功能底线（除真机 A 外）已达成 |
| ⑥b 对话外壳 | **已完成**。按第 12 节把主页改为对话流（计划卡 / 结果卡）；新增“我的”页（人物切换 + 四位 PIN、访客模式、证据面板开关）；“空间”“场景”两页先用现有卡片搭出骨架 | 对话流走通休息 → 确认 → 停止；PIN 与访客模式可用；原始活动只在证据面板出现；测试全部通过 | 只改页面结构与 `services/`，不改后端契约（PIN 与访客上下文除外，需 `gen-api.sh`） |
| C 视觉整理 | 按 `docs/ui-polish.md` 清单美化；只改 `theme/`、`components/`、`features/` | 两种尺寸截图前后对比；测试全部通过；来源标注仍清晰可见 | **已完成**（天蓝色主题） |
| ⑦ 整晚服务 | 模拟时钟、夜间阶段、渐进唤醒；一个 `serviceId` 贯穿整晚 | 定时任务不重复执行；停止取消剩余任务 | **已完成**（模拟时钟；见 `docs/architecture.md` 规则 25–30） |
| ⑧ 补齐模块 | 主 Agent、Space Execution Agent、人物记忆、能源规则及所需 Harness 能力 | 每个模块一条真实工作路径、明确输入输出、调用证据 | **已完成**；如实描述见 0.4 |
| ⑨ 补齐入口细节 | 演示脚本化与稳定性（一键演示数据、固定演示时段）、空态插画与提示淡出、“场景”页展示 1+2 Agent 场景卡；旧 HTML 清单只作参考 | 一页完成、一页验收；场景状态标签与真实实现一致 | **已完成**；旧 HTML 清单待用户提供旧页面 |
| D 演示打包 | Development Build 装到平板；录屏三段（用户触发、事件调整、手动停止）；PDF 主张对证据表 | 每条主张有对应证据；模拟与真实来源分开标注 | **云端部分已完成**：`e2e/record_demo.py`、`scripts/build_evidence.py`、`docs/device-build.md`；平板构建待设备 |

两条底线：**功能底线 = A + B + ⑥（含第一批规则链路）；AI 演示底线 = 再加 ⑤。** 产品形态底线 = 再加 ⑥b + C（已达成）。**“1+2 Agent 已实现”底线 = ⑧（已达成）。**

不能因为建立了目录或类名，就宣称相应 Agent 已经实现。功能声明必须对应真实调用轨迹和测试。

## 9. T6 已完成：下一位 AI 的接手边界

T1–T6 本地工程化冻结已完成。下一位 AI 首先读 `docs/status.md`和`docs/technology-architecture.md`，不要重做基础设施，也不要继续增加技术栈。

### 9.1 本地冻结证据

| 项 | 结果 |
|---|---|
| Compose 全栈 | PostgreSQL、Redis、migration、API、Outbox Publisher、Activity Projector 一次启动，API healthy |
| Worker 链路 | 7/7 Outbox 发布与消费；Worker 重启后 `domain_events` 与 `consumer_receipts` 数量不变 |
| 数据库迁移 | 空库 0001→0003；0003→0002→0003 回退再恢复通过 |
| 后端组合 | 内存+legacy 127/18 skip；PostgreSQL+legacy 141/4 skip；PostgreSQL+Redis+LangGraph 145/145 |
| Agent 等价 | Legacy / LangGraph 5 组输入全部等价 |
| 前端与契约 | 前端 31/31 + 类型检查；OpenAPI → TS 重新生成无 diff |
| Docker API E2E | Playwright 20/20；含整晚、模型桩、停止竞态与断开后端 |
| 证据表 | `docs/evidence.md` 与 `output/pdf/LivingMind-主张证据表.pdf`；5 页逐页渲染检查 |

### 9.2 外部状态与剩余验收

1. **真机**：有 iPad 或安卓平板后，按 `docs/device-build.md` 做 Expo Go / Development Build、横竖屏、局域网、断网和完整闭环验收。
2. **GitHub 托管 CI（已完成）**：运行 `35333253707` 的 6 个 Job 全绿；覆盖三套后端组合、迁移、契约、前端和 Docker API E2E 20/20。
3. **可选指标**：DeepSeek 多次延迟统计按 `docs/project-metrics.md` 执行；当前仍只有 2035 ms 单次真实样本，不得虚构提升比例。
4. **能源口径**：用户已确认以给定固定日数据为准，不重训、不复现 MATD3；只标注“已提供的离线仿真结果”。
5. **旧 HTML**：已不是新 Expo 项目完成的前置；只在用户再提供具体旧页面并要求对照时处理。

### 9.3 复现入口

```bash
docker compose up -d
docker compose ps
apps/mobile/e2e/.venv/bin/python apps/mobile/e2e/run_e2e.py --external-backend http://127.0.0.1:8000
./scripts/gen-api.sh && git diff --exit-code -- packages/api-client
python scripts/build_evidence.py --pdf
docker compose down
```

不写 Kafka 实现，不把设备状态放 Redis，不让 LangGraph 绕过 Harness / Executor，不把本地 CI 配置描述成 GitHub 已运行。

## 10. 禁止事项

- 不整体重写现有 App 或 FastAPI 服务。
- 不在一个批次里同时引入 LangGraph、PostgreSQL、Redis 和事件总线；严格按 T1–T6 逐步验收。
- 不让 LangGraph 节点绕过 Harness / Executor 直接写设备。
- 不用 Redis 保存唯一业务事实，不用事件总线发送设备控制命令。
- 不为“技术栈看起来丰富”增加没有真实调用、测试和故障路径的服务。
- 不复制旧项目的 `.env`、密钥、数据库或大批无关代码。
- 不把 Mock、预录结果、测试替身描述成在线模型调用。
- 不创建远程仓库、不推送、不部署、不发布，除非用户另行明确授权。
- 不修改或删除用户的原始汇报材料和旧项目。

## 11. 接手 AI 的交付格式

每次完成后必须给出：

1. 本次只完成了哪个步骤。
2. 修改的文件和关键设计。
3. 启动与复现方法。
4. 自动检查、真机/模拟器/浏览器检查及各自结果。
5. 哪些仍是模拟、预留或未验证。
6. 当前提交哈希和工作区是否干净。
7. 下一步建议，但未经确认不继续执行。

可直接给下一位 AI 的指令：

> 请先阅读仓库根目录 `AGENT-HANDOFF.md`（尤其第 0.2、0.3、9 节），再依次阅读 `docs/technology-architecture.md`、`docs/status.md`、`README.md`、`docs/project-metrics.md`、`docs/acceptance.md` 与 `docs/architecture.md`。保留现有实现和提交历史。T1–T6、本地验证及 GitHub 托管 CI 均已完成，不要重复搭建基础设施，也不要新增 Kafka、重构 Agent/Harness/Executor、复现或重训 MATD3。下一步只在用户明确授权后选择一项执行：①依据 `docs/device-build.md` 做 iPad/Android 真机验收；②按用户要求运行 DeepSeek 多样本指标评测；③后续提交若导致 CI 失败，只修复对应回归。描述能力时遵守第 0.4 节与 `docs/project-metrics.md` 的如实口径；真实设备接入、真机安装和多样本模型指标在实际完成前必须标为未验证。不要自行部署或扩大业务范围。

## 12. 产品界面方向（用户已确认，2026-09-17）

以下是用户确认的产品形态目标。它决定 ⑥b、C、⑨ 的内容，不改变第 3 节的架构边界，也不提前任何后端步骤。

### 12.1 原则

- 用户默认看到的界面只有动画与交互，不显示 `action_executed` 这类原始活动细节。
- 原始调用轨迹保留在**证据面板**：从“我的”页开关打开，默认关闭。复赛 PDF 第 6 页与评委追问都依赖它，不得删除。
- 视觉目标：动画流畅、有 LivingMind Logo、颜色干净明亮、高端克制；具体清单见 `docs/ui-polish.md`。
- 来源标注（前端模拟 / 规则 / 模型 / 规则降级 / 虚拟设备 / 模拟事件）在产品界面上可以变得含蓄，但不能消失。

### 12.2 四个入口

| 入口 | 内容 | 依赖的后端步骤 |
|---|---|---|
| 对话（主页） | 聊天流：用户一句话 → AI 回复一张**计划卡**（可确认）→ 执行后回一张**结果卡**；停止按钮；语音/打字切换（首版只做打字，语音按钮为占位并标注“后续接入”） | ⑤ 已有；语音 ASR 后置 |
| 空间 | 可控设备状态、当前服务、节能档位 | 已有；节能档位依赖 ⑧ |
| 场景 | 主动服务场景库，每张卡带状态标签；点开看该场景的执行记录（人话，如“22:10 室温升高，空调降到 24°C”） | ⑥ |
| 我的 | 当前人物、个人偏好（只能看到自己的）、切换人物（四位 PIN）、访客模式、证据面板开关 | 已有；偏好编辑依赖 ⑧ |

对话主页只是换了容器：计划、确认、停止、来源标注的逻辑与接口不变。

**⑥b 已实现上述四个入口的骨架；⑧ 补上了节能与偏好编辑**（语音仍为占位）。

### 12.3 身份与访客

- “切换人物 + 四位 PIN”是演示用的人物切换，后端仍是演示身份，**不是认证**。PIN 存在后端种子数据里，只用于演示防误切换。
- 没人选择自己时，使用**访客/空间公共上下文**：只用空间默认设置，没有私人偏好，动作需确认后执行。
- 智能音箱接入时一律按访客上下文处理；谁要私人偏好就在平板上选自己。**声纹识别不在范围内**，此决定已确认，不再反复讨论。

### 12.4 场景库首版（3 个）

| 场景 | 状态标签 | 何时可标“已实现” |
|---|---|---|
| 我想休息 | 已实现 | 现在 |
| 室温变化后自动调整 | 已实现（网页与测试验证，真机未验证） | ⑥ 已完成 |
| 起床渐进唤醒 | 已实现（模拟时钟，网页与测试验证，真机未验证） | ⑦ 已完成 |

场景卡不是写死的“示例”，状态标签必须与真实实现一致；执行记录来自后端活动数据筛选，不得预录。

### 12.5 节能显示的限制

- ⑧ 已实现：计划卡与“空间”页显示能源建议、估算负荷档位（标注“规则估算，非实测”）与原因；可切换舒适优先 / 节能模式。
- **不显示节省百分比或金额**（见第 10 节与设计规范）。
